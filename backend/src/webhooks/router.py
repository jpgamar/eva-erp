"""Stripe webhook handler for ERP custom deal subscriptions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from src.common.config import settings
from src.common.database import async_sessionmaker, engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for ERP custom deal subscriptions."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    secret = (settings.stripe_webhook_secret_erp or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]

    # Only handle events from ERP custom deals (check metadata)
    metadata = data_object.get("metadata") or {}
    subscription_metadata = {}

    # For invoice events, get metadata from the subscription
    if event_type.startswith("invoice."):
        sub_id = data_object.get("subscription")
        if sub_id:
            stripe.api_key = settings.eva_stripe_secret_key
            try:
                sub = stripe.Subscription.retrieve(sub_id)
                subscription_metadata = sub.get("metadata") or {}
            except stripe.error.StripeError as exc:
                logger.warning("Failed to retrieve subscription %s metadata: %s", sub_id, exc)
                subscription_metadata = {}

    source = metadata.get("source") or subscription_metadata.get("source")
    if source != "erp_custom_deal":
        # Not an ERP custom deal — ignore silently
        return {"received": True, "handled": False}

    empresa_id = metadata.get("empresa_id") or subscription_metadata.get("empresa_id")
    if not empresa_id:
        logger.warning("Webhook %s missing empresa_id in metadata", event_type)
        return {"received": True, "handled": False}

    async with async_sessionmaker(engine)() as db:
        try:
            if event_type == "checkout.session.completed":
                await _handle_checkout_completed(db, empresa_id, data_object)
            elif event_type == "invoice.paid":
                await _handle_invoice_paid(db, empresa_id, data_object, subscription_metadata)
            elif event_type == "invoice.payment_failed":
                await _handle_payment_failed(db, empresa_id)
            elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
                await _handle_subscription_change(db, empresa_id, data_object)
            await db.commit()
        except Exception:
            logger.exception("Error handling webhook %s for empresa %s", event_type, empresa_id)
            await db.rollback()
            # Re-raise so Stripe gets a 500 and retries the event
            raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True, "handled": True}


async def _handle_checkout_completed(db, empresa_id: str, session: dict):
    """Customer completed checkout — activate subscription."""
    from src.empresas.models import Empresa

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        logger.warning("Empresa %s not found for checkout.session.completed", empresa_id)
        return

    subscription_id = session.get("subscription")
    if subscription_id:
        stripe.api_key = settings.eva_stripe_secret_key
        sub = stripe.Subscription.retrieve(subscription_id)
        empresa.stripe_subscription_id = subscription_id
        empresa.subscription_status = sub.get("status", "active")
        period_end = sub.get("current_period_end")
        if period_end:
            empresa.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    customer_id = session.get("customer")
    if customer_id and not empresa.stripe_customer_id:
        empresa.stripe_customer_id = customer_id

    db.add(empresa)
    await db.flush()
    logger.info("Empresa %s subscription activated: %s", empresa.name, subscription_id)


async def _handle_invoice_paid(db, empresa_id: str, invoice: dict, subscription_metadata: dict):
    """Recurring payment succeeded — stamp CFDI and send email."""
    from src.empresas.models import Empresa
    from src.facturas.models import Factura
    from src.facturas.schemas import FacturaCreate, FacturaLineItem
    from src.eva_billing.models import EvaBillingRecord
    from src.eva_billing.service import EvaBillingService, EvaBillingCustomer

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        logger.warning("Empresa %s not found for invoice.paid", empresa_id)
        return

    # Update period
    sub_id = invoice.get("subscription")
    if sub_id:
        stripe.api_key = settings.eva_stripe_secret_key
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            empresa.subscription_status = sub.get("status", "active")
            period_end = sub.get("current_period_end")
            if period_end:
                empresa.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
            empresa.last_paid_date = datetime.now(timezone.utc).date()
            db.add(empresa)
            await db.flush()
        except Exception:
            logger.exception("Failed to update subscription period for empresa %s", empresa_id)

    # Check idempotency — don't re-stamp for the same invoice
    stripe_invoice_id = invoice.get("id")
    existing = await db.scalar(
        select(EvaBillingRecord).where(EvaBillingRecord.stripe_invoice_id == stripe_invoice_id).limit(1)
    )
    if existing:
        logger.info("Invoice %s already processed for empresa %s", stripe_invoice_id, empresa.name)
        return

    # Check fiscal info
    if not empresa.rfc or not empresa.razon_social or not empresa.regimen_fiscal:
        logger.warning("Skipping CFDI for empresa %s — fiscal info incomplete (rfc=%s)", empresa.name, empresa.rfc)
        return

    # Stamp CFDI
    amount_total = int(invoice.get("total") or invoice.get("amount_paid") or 0)
    description = subscription_metadata.get("description") or f"Servicio EvaAI — {empresa.name}"
    recipient_emails = [e.strip().lower() for e in (empresa.billing_recipient_emails or []) if isinstance(e, str) and e.strip()]
    if not recipient_emails and empresa.email:
        recipient_emails = [empresa.email.strip().lower()]

    # Determine if retention applies (persona moral = regimen 601)
    is_persona_moral = empresa.regimen_fiscal in ("601", "603", "610", "620", "622", "623", "624", "628")
    base_subtotal_minor = amount_total  # For non-retention, base = total

    if is_persona_moral:
        # Reverse-compute base from payable total (same as Eva billing)
        from decimal import Decimal, ROUND_HALF_UP
        factor = (Decimal("1.00") + Decimal("0.16") - Decimal("0.0125") - Decimal("0.106667")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        base_subtotal_minor = int((Decimal(amount_total) / factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    try:
        customer = EvaBillingCustomer(
            legal_name=empresa.razon_social or empresa.name,
            tax_id=empresa.rfc,
            tax_regime=empresa.regimen_fiscal or "601",
            postal_code="11560",  # Default — should be on empresa model eventually
            cfdi_use="G03",
            person_type="persona_moral" if is_persona_moral else "persona_fisica",
        )

        svc = EvaBillingService()
        factura_data = FacturaCreate(
            customer_name=customer.legal_name,
            customer_rfc=customer.tax_id,
            customer_tax_system=customer.tax_regime,
            customer_zip=customer.postal_code,
            use=customer.cfdi_use,
            payment_form="04",  # Tarjeta de credito
            payment_method="PUE",
            line_items=[
                FacturaLineItem(
                    product_key="81112100",
                    description=description,
                    quantity=1,
                    unit_price=float(base_subtotal_minor) / 100,
                    tax_rate=0.16,
                    isr_retention=0.0125 if is_persona_moral else None,
                    iva_retention=0.106667 if is_persona_moral else None,
                )
            ],
            currency="MXN",
            account_id=empresa.id,
        )

        from src.facturas import service as facturapi_svc
        payload = facturapi_svc.build_facturapi_payload(factura_data)
        api_result = await facturapi_svc.create_invoice(payload)

        # Create Factura record
        factura = Factura(
            facturapi_id=api_result["id"],
            cfdi_uuid=api_result.get("uuid"),
            customer_name=customer.legal_name,
            customer_rfc=customer.tax_id,
            customer_tax_system=customer.tax_regime,
            customer_zip=customer.postal_code,
            use=customer.cfdi_use,
            payment_form="04",
            payment_method="PUE",
            line_items_json=[],
            subtotal=float(base_subtotal_minor) / 100,
            tax=float(base_subtotal_minor) * 0.16 / 100,
            total=float(amount_total) / 100,
            currency="MXN",
            status=api_result.get("status", "valid"),
            issued_at=datetime.now(timezone.utc),
        )
        db.add(factura)
        await db.flush()

        # Create billing record
        record = EvaBillingRecord(
            account_id=empresa.id,  # Use empresa_id as account_id for ERP custom deals
            source_type="subscription_invoice",
            idempotency_key=f"erp-deal:{empresa_id}:{stripe_invoice_id}",
            stripe_invoice_id=stripe_invoice_id,
            stripe_payment_intent_id=invoice.get("payment_intent"),
            stripe_subscription_id=sub_id,
            stripe_customer_id=invoice.get("customer"),
            factura_id=factura.id,
            status="issued",
            recipient_email=recipient_emails[0] if recipient_emails else None,
            currency="MXN",
            total=float(amount_total) / 100,
            metadata_json={
                "source": "erp_custom_deal",
                "empresa_id": empresa_id,
                "description": description,
                "recipient_emails": recipient_emails,
            },
        )
        db.add(record)
        await db.flush()

        # Send email with attachments
        from decimal import Decimal as Dec
        email_status, email_error = await svc._send_invoice_email(
            recipient_emails=recipient_emails,
            customer=customer,
            factura=factura,
            total=Dec(str(float(amount_total) / 100)),
        )
        record.email_status = email_status
        record.email_error = email_error
        if email_status == "sent":
            record.email_sent_at = datetime.now(timezone.utc)
            record.status = "email_sent"
        db.add(record)
        await db.flush()

        logger.info(
            "CFDI stamped for empresa %s: uuid=%s, email=%s",
            empresa.name, factura.cfdi_uuid, email_status,
        )

    except Exception:
        logger.exception("Failed to stamp CFDI for empresa %s invoice %s", empresa.name, stripe_invoice_id)


async def _handle_payment_failed(db, empresa_id: str):
    """Payment failed — update status."""
    from src.empresas.models import Empresa

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        return
    empresa.subscription_status = "past_due"
    db.add(empresa)
    await db.flush()
    logger.warning("Payment failed for empresa %s", empresa.name)


async def _handle_subscription_change(db, empresa_id: str, subscription: dict):
    """Subscription updated or deleted."""
    from src.empresas.models import Empresa

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        return

    status = subscription.get("status", "canceled")
    empresa.subscription_status = status

    period_end = subscription.get("current_period_end")
    if period_end:
        empresa.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    if status == "canceled":
        empresa.stripe_subscription_id = None

    db.add(empresa)
    await db.flush()
    logger.info("Subscription %s for empresa %s: status=%s", subscription.get("id"), empresa.name, status)
