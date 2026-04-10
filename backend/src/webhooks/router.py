"""Stripe webhook handler for ERP custom deal subscriptions."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from src.common.config import settings
from src.common.database import async_sessionmaker, engine
from src.eva_billing.service import (
    _compute_quote,
    is_fiscal_complete,
    resolve_retention_applicable,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


async def _report_billing(
    category: str, severity: str, title: str, summary: str,
    empresa_id: str | None, empresa_name: str | None, invoice_id: str | None,
) -> None:
    """Fire-and-forget billing issue report to monitoring dashboard."""
    try:
        from src.eva_platform.billing_monitor import report_billing_issue
        await report_billing_issue(
            category=category, severity=severity, title=title, summary=summary,
            empresa_id=empresa_id, empresa_name=empresa_name, stripe_invoice_id=invoice_id,
        )
    except Exception:
        logger.warning("Failed to report billing issue to monitoring", exc_info=True)


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

    # Session 1: Handle subscription status updates (synchronous, returns 200 to Stripe)
    async with async_sessionmaker(engine)() as db:
        try:
            if event_type == "checkout.session.completed":
                await _handle_checkout_completed(db, empresa_id, data_object)
            elif event_type == "invoice.paid":
                await _handle_invoice_paid_status(db, empresa_id, data_object)
            elif event_type == "invoice.payment_failed":
                await _handle_payment_failed(db, empresa_id)
            elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
                await _handle_subscription_change(db, empresa_id, data_object)
            await db.commit()
        except Exception as exc:
            logger.exception("Error handling webhook %s for empresa %s", event_type, empresa_id)
            await db.rollback()
            from src.eva_platform.billing_monitor import report_billing_issue
            asyncio.create_task(report_billing_issue(
                category="billing_webhook_error",
                severity="high",
                title=f"Stripe webhook {event_type} failed",
                summary=str(exc)[:500],
                empresa_id=empresa_id,
                context={"event_type": event_type},
            ))
            raise HTTPException(status_code=500, detail="Webhook processing failed")

    # Session 2: Background CFDI stamping for invoice.paid (separate DB session)
    if event_type == "invoice.paid":
        asyncio.create_task(
            _stamp_cfdi_background(empresa_id, data_object, subscription_metadata)
        )

    return {"received": True, "handled": True}


async def _handle_checkout_completed(db, empresa_id: str, session: dict):
    """Customer completed checkout — activate subscription + mark PaymentLink as paid."""
    from src.empresas.models import Empresa, PaymentLink

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

    # Mark corresponding PaymentLink as paid
    metadata = session.get("metadata") or {}
    link_token = metadata.get("payment_link_token")
    if link_token:
        result = await db.execute(
            select(PaymentLink).where(PaymentLink.token == link_token)
        )
        link = result.scalar_one_or_none()
        if link and link.status == "active":
            link.status = "paid"
            link.paid_at = datetime.now(timezone.utc)
            link.stripe_checkout_session_id = session.get("id")
            db.add(link)
            await db.flush()
            logger.info("PaymentLink %s marked as paid", link_token)

    logger.info("Empresa %s subscription activated: %s", empresa.name, subscription_id)


async def _handle_invoice_paid_status(db, empresa_id: str, invoice: dict):
    """Update subscription period on invoice.paid (CFDI handled in background)."""
    from src.empresas.models import Empresa

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        logger.warning("Empresa %s not found for invoice.paid", empresa_id)
        return

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


async def _stamp_cfdi_background(empresa_id: str, invoice: dict, subscription_metadata: dict):
    """Stamp CFDI in a separate DB session (fire-and-forget from webhook).

    If stamping fails, logs the error. Admin can re-stamp from /facturas.
    """
    from src.empresas.models import Empresa
    from src.eva_billing.models import EvaBillingRecord
    from src.eva_billing.schemas import (
        EvaBillingCustomer,
        EvaBillingStampCharge,
        EvaBillingStampRequest,
        EvaBillingStampSource,
    )
    from src.eva_billing.service import EvaBillingService

    stripe_invoice_id = invoice.get("id")

    async with async_sessionmaker(engine)() as db:
        try:
            empresa = await db.get(Empresa, empresa_id)
            if not empresa:
                logger.warning("CFDI background: Empresa %s not found", empresa_id)
                await _report_billing("billing_webhook_error", "high",
                    f"Empresa not found for invoice", f"empresa_id={empresa_id} not in DB",
                    empresa_id, None, stripe_invoice_id)
                return

            # Check idempotency
            existing = await db.scalar(
                select(EvaBillingRecord)
                .where(EvaBillingRecord.stripe_invoice_id == stripe_invoice_id)
                .limit(1)
            )
            if existing:
                logger.info("CFDI background: Invoice %s already processed for empresa %s", stripe_invoice_id, empresa.name)
                return

            # Determine retention from metadata (preferred) or empresa fields (legacy)
            meta_retention = subscription_metadata.get("retention_applicable")
            meta_base = subscription_metadata.get("base_subtotal_minor")

            if meta_retention is not None and meta_base is not None:
                # New path: metadata stored by create_checkout_session
                retention_applicable = meta_retention in (True, "True", "true")
                base_subtotal_minor = int(meta_base)
            else:
                # Legacy path: infer from empresa fields
                retention = resolve_retention_applicable(empresa.person_type, empresa.regimen_fiscal)
                if retention is None:
                    logger.warning(
                        "CFDI background: Cannot determine retention for empresa %s (person_type=%s, regimen=%s). Skipping CFDI.",
                        empresa.name, empresa.person_type, empresa.regimen_fiscal,
                    )
                    await _report_billing("billing_fiscal_incomplete", "medium",
                        f"CFDI skipped — tipo de persona desconocido: {empresa.name}",
                        f"person_type={empresa.person_type}, regimen={empresa.regimen_fiscal}",
                        empresa_id, empresa.name, stripe_invoice_id)
                    return
                retention_applicable = retention
                amount_total = int(invoice.get("total") or invoice.get("amount_paid") or 0)
                if retention_applicable:
                    # Reverse-compute base from payable total
                    from decimal import Decimal, ROUND_HALF_UP
                    from src.eva_billing.service import IVA_RATE, ISR_RETENTION_RATE, IVA_RETENTION_RATE
                    factor = (Decimal("1.00") + IVA_RATE - ISR_RETENTION_RATE - IVA_RETENTION_RATE).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    base_subtotal_minor = int(
                        (Decimal(amount_total) / factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    )
                else:
                    base_subtotal_minor = amount_total

            # Check fiscal completeness — skip CFDI if incomplete
            if not is_fiscal_complete(
                empresa.rfc, empresa.razon_social, empresa.regimen_fiscal,
                empresa.fiscal_postal_code, empresa.cfdi_use, empresa.person_type,
            ):
                logger.warning(
                    "CFDI background: Fiscal info incomplete for empresa %s (rfc=%s). Skipping CFDI.",
                    empresa.name, empresa.rfc,
                )
                await _report_billing("billing_fiscal_incomplete", "medium",
                    f"CFDI skipped — datos fiscales incompletos: {empresa.name}",
                    f"rfc={empresa.rfc}, razon_social={empresa.razon_social}",
                    empresa_id, empresa.name, stripe_invoice_id)
                return

            # Compute quote using centralized logic
            quote = _compute_quote(base_subtotal_minor, retention_applicable=retention_applicable)
            description = subscription_metadata.get("description") or f"Servicio EvaAI — {empresa.name}"
            sub_id = invoice.get("subscription")

            recipient_emails = [
                e.strip().lower() for e in (empresa.billing_recipient_emails or [])
                if isinstance(e, str) and e.strip()
            ]
            if not recipient_emails and empresa.email:
                recipient_emails = [empresa.email.strip().lower()]

            # Resolve person_type for EvaBillingCustomer
            person_type = empresa.person_type
            if not person_type:
                person_type = "persona_moral" if retention_applicable else "persona_fisica"

            stamp_request = EvaBillingStampRequest(
                account_id=empresa.id,
                owner_email=recipient_emails[0] if recipient_emails else "no-reply@goeva.ai",
                recipient_emails=recipient_emails,
                idempotency_key=f"erp-deal:{empresa_id}:{stripe_invoice_id}",
                source=EvaBillingStampSource(
                    type="subscription_invoice",
                    stripe_invoice_id=stripe_invoice_id,
                    stripe_payment_intent_id=invoice.get("payment_intent"),
                    stripe_subscription_id=sub_id,
                    stripe_customer_id=invoice.get("customer"),
                ),
                customer=EvaBillingCustomer(
                    legal_name=empresa.razon_social or empresa.name,
                    tax_id=empresa.rfc,
                    tax_regime=empresa.regimen_fiscal,
                    postal_code=empresa.fiscal_postal_code,
                    cfdi_use=empresa.cfdi_use,
                    person_type=person_type,
                ),
                charge=EvaBillingStampCharge(
                    currency="MXN",
                    description=description,
                    payable_total_minor=quote.payable_total_minor,
                    base_subtotal_minor=quote.base_subtotal_minor,
                    payment_form="04",
                    payment_method="PUE",
                    retention_applicable=retention_applicable,
                ),
            )

            svc = EvaBillingService()
            result = await svc.stamp(db, stamp_request)
            await db.commit()

            logger.info(
                "CFDI stamped for empresa %s: uuid=%s, email=%s",
                empresa.name, result.cfdi_uuid, result.email_status,
            )

        except Exception as exc:
            logger.exception(
                "CFDI background: Failed to stamp for empresa %s invoice %s",
                empresa_id, stripe_invoice_id,
            )
            try:
                await db.rollback()
            except Exception:
                pass
            await _report_billing("billing_cfdi_failure", "critical",
                f"CFDI stamp failed: {getattr(empresa, 'name', empresa_id)}",
                f"invoice={stripe_invoice_id}, error={str(exc)[:300]}",
                empresa_id, getattr(empresa, "name", None), stripe_invoice_id)


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
