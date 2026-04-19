from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.mx_postal_codes import state_from_zip
from src.eva_billing.cedular import CedularRule, cedular_rate, resolve_cedular
from src.eva_billing.models import EvaBillingRecord
from src.eva_billing.schemas import (
    EvaBillingCustomer,
    EvaBillingDisplayLine,
    EvaBillingQuoteRequest,
    EvaBillingQuoteResponse,
    EvaBillingRefundRequest,
    EvaBillingStampRequest,
    EvaBillingStampResponse,
    EvaBillingStatusItem,
    EvaBillingStatusResponse,
)
from src.facturas import service as facturapi
from src.facturas.models import Factura
from src.facturas.schemas import FacturaCreate, FacturaLineItem

logger = logging.getLogger(__name__)

IVA_RATE = Decimal("0.16")
ISR_RETENTION_RATE = Decimal("0.0125")
IVA_RETENTION_RATE = Decimal("0.106667")
SERVICE_PRODUCT_KEY = "81112100"

# Provider regime (the issuer of the CFDI). Today EvaAI is Gustavo Zermeño
# operating as persona física under RESICO. If we incorporate as a moral
# entity we'll move this to config.
PROVIDER_REGIME = "resico_pf"

# Regimen fiscal codes that indicate persona moral
PERSONA_MORAL_REGIMENES = frozenset({"601", "603", "610", "620", "622", "623", "624", "628"})


def resolve_retention_applicable(
    person_type: str | None,
    regimen_fiscal: str | None,
) -> bool | None:
    """Determine if IVA/ISR retentions apply based on persona type.

    Returns True (persona moral), False (persona fisica), or None (unknown).
    Callers decide policy: checkout blocks on None, webhook skips CFDI.
    """
    if person_type == "persona_moral":
        return True
    if person_type == "persona_fisica":
        return False
    # person_type not set — try to infer from regimen_fiscal
    if regimen_fiscal and regimen_fiscal in PERSONA_MORAL_REGIMENES:
        return True
    if regimen_fiscal:
        # Known regimen but not persona_moral → persona fisica
        return False
    # Both null — unknown
    return None


def is_fiscal_complete(
    rfc: str | None,
    razon_social: str | None,
    regimen_fiscal: str | None,
    fiscal_postal_code: str | None,
    cfdi_use: str | None,
    person_type: str | None,
) -> bool:
    """Check if all fiscal fields required for CFDI stamping are present."""
    return all([
        rfc,
        razon_social,
        regimen_fiscal,
        fiscal_postal_code,
        cfdi_use,
        person_type or (regimen_fiscal and regimen_fiscal in PERSONA_MORAL_REGIMENES),
    ])


def _minor_to_major(amount_minor: int) -> Decimal:
    return (Decimal(amount_minor) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _major_to_minor(amount_major: Decimal) -> int:
    return int((amount_major * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _compute_quote(
    base_subtotal_minor: int,
    *,
    retention_applicable: bool,
    customer_zip: str | None = None,
    provider_regime: str = PROVIDER_REGIME,
) -> EvaBillingQuoteResponse:
    """Compute all retentions + final payable.

    Federal retentions (ISR 1.25% + IVA 2/3) always apply when the customer
    is a persona moral (``retention_applicable=True``).

    State-level cedular retention (e.g., Guanajuato 2%) applies when:
      - ``retention_applicable`` is True (PM customer), AND
      - ``customer_zip`` falls inside a state with a verified cedular rule
        for the provider's regime (see ``eva_billing.cedular``).

    Passing ``customer_zip=None`` (or a non-cedular ZIP) yields the legacy
    two-retention behavior — callers that don't know the ZIP are
    unaffected.
    """
    base_major = _minor_to_major(base_subtotal_minor)
    iva_major = (base_major * IVA_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    isr_major = Decimal("0.00")
    iva_ret_major = Decimal("0.00")
    cedular_major = Decimal("0.00")
    cedular_rule: CedularRule | None = None

    if retention_applicable:
        isr_major = (base_major * ISR_RETENTION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        iva_ret_major = (base_major * IVA_RETENTION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cedular_rule = resolve_cedular(customer_zip, provider_regime)
        if cedular_rule:
            # ``resolve_cedular`` only returns a rule when the rate for the
            # given regime is non-None, so ``cedular_rate`` here is always
            # a valid Decimal.
            rate = cedular_rate(cedular_rule, provider_regime)
            if rate is not None:
                cedular_major = (base_major * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_major = (base_major + iva_major - isr_major - iva_ret_major - cedular_major).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    payable_minor = _major_to_minor(total_major)
    iva_minor = _major_to_minor(iva_major)
    isr_minor = _major_to_minor(isr_major)
    iva_ret_minor = _major_to_minor(iva_ret_major)
    cedular_minor = _major_to_minor(cedular_major)

    display_lines = [
        EvaBillingDisplayLine(label="Plan base", amount_minor=base_subtotal_minor),
        EvaBillingDisplayLine(label="IVA", amount_minor=iva_minor),
    ]
    if retention_applicable:
        total_retentions_minor = isr_minor + iva_ret_minor + cedular_minor
        display_lines.append(
            EvaBillingDisplayLine(label="Retenciones aplicables", amount_minor=-total_retentions_minor)
        )
        if cedular_rule and cedular_minor > 0:
            # Extra transparency line when cedular applies so the operator
            # can see exactly which state levied it.
            display_lines.append(
                EvaBillingDisplayLine(
                    label=f"  · Cedular {cedular_rule.label} ({cedular_rule.legal_article})",
                    amount_minor=-cedular_minor,
                )
            )
    display_lines.append(EvaBillingDisplayLine(label="Total a pagar", amount_minor=payable_minor))

    cedular_rate_out: Decimal | None = None
    if cedular_rule and cedular_minor > 0:
        cedular_rate_out = cedular_rate(cedular_rule, provider_regime)

    return EvaBillingQuoteResponse(
        retention_applicable=retention_applicable,
        currency="MXN",
        base_subtotal_minor=base_subtotal_minor,
        iva_minor=iva_minor,
        isr_retention_minor=isr_minor,
        iva_retention_minor=iva_ret_minor,
        payable_total_minor=payable_minor,
        display_lines=display_lines,
        cedular_retention_minor=cedular_minor,
        cedular_state_code=cedular_rule.state_code if cedular_rule and cedular_minor > 0 else None,
        cedular_rate=cedular_rate_out,
    )


class EvaBillingService:
    @staticmethod
    def _resolve_recipient_emails(owner_email: str, recipient_emails: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for email in recipient_emails or []:
            normalized_email = email.strip().lower()
            if not normalized_email or normalized_email in seen:
                continue
            seen.add(normalized_email)
            normalized.append(normalized_email)
        fallback = owner_email.strip().lower()
        if not normalized and fallback:
            normalized.append(fallback)
        return normalized

    def quote(self, payload: EvaBillingQuoteRequest) -> EvaBillingQuoteResponse:
        retention_applicable = payload.customer.person_type == "persona_moral"
        return _compute_quote(
            payload.charge.base_subtotal_minor,
            retention_applicable=retention_applicable,
            customer_zip=payload.customer.postal_code,
        )

    async def stamp(self, db: AsyncSession, payload: EvaBillingStampRequest) -> EvaBillingStampResponse:
        """Enqueue a CFDI stamp.

        Creates a factura row in ``status='pending_stamp'`` with the
        idempotency key and commits (via the caller's session). The
        FacturAPI HTTP call happens asynchronously in the outbox worker
        (see ``src/facturas/outbox.py``). This eliminates the F-4 class
        of bug where FacturAPI success + DB commit failure lost the row.

        The response status will be ``'pending_stamp'`` on first call.
        Clients (Eva platform bridge, webhook) should treat the request
        as accepted and either poll ``/internal/eva-billing/status/{account_id}``
        or wait for the invoice email to arrive.

        Idempotent replays (same ``idempotency_key``) return the existing
        record — if the outbox already stamped it, the response includes
        the ``cfdi_uuid`` and ``pdf_url`` as before.
        """
        existing = await self._find_existing_record(db, payload)
        if existing and existing.factura_id:
            factura = await db.get(Factura, existing.factura_id)
            if factura:
                return EvaBillingStampResponse(
                    status=existing.status,
                    factura_id=factura.id,
                    cfdi_uuid=factura.cfdi_uuid,
                    pdf_url=factura.pdf_url,
                    xml_url=factura.xml_url,
                    email_status=existing.email_status,
                )

        quote_customer_zip = (
            payload.customer.postal_code
            if payload.charge.cedular_retention_applicable is not False
            else None
        )
        quote = _compute_quote(
            payload.charge.base_subtotal_minor,
            retention_applicable=payload.charge.retention_applicable,
            customer_zip=quote_customer_zip,
        )
        if abs(quote.payable_total_minor - payload.charge.payable_total_minor) > 100:
            raise ValueError(
                f"Quote total ({quote.payable_total_minor}) does not match Stripe payable amount "
                f"({payload.charge.payable_total_minor}), diff={abs(quote.payable_total_minor - payload.charge.payable_total_minor)}"
            )
        recipient_emails = self._resolve_recipient_emails(payload.owner_email, payload.recipient_emails)

        # Resolve the cedular rule (if any) so we can label the local_taxes
        # line cleanly on the CFDI (e.g., "Cedular GTO" instead of "ISR").
        cedular_rule = resolve_cedular(quote_customer_zip, PROVIDER_REGIME)
        line_items = [
            FacturaLineItem(
                product_key=SERVICE_PRODUCT_KEY,
                description=payload.charge.description,
                quantity=1,
                unit_price=_minor_to_major(payload.charge.base_subtotal_minor),
                tax_rate=IVA_RATE,
                isr_retention=ISR_RETENTION_RATE if payload.charge.retention_applicable else None,
                iva_retention=IVA_RETENTION_RATE if payload.charge.retention_applicable else None,
                cedular_rate=quote.cedular_rate if quote.cedular_retention_minor > 0 else None,
                cedular_label=cedular_rule.facturapi_type if cedular_rule and quote.cedular_retention_minor > 0 else None,
            )
        ]
        factura_data = FacturaCreate(
            account_id=payload.account_id,
            customer_name=payload.customer.legal_name,
            customer_rfc=payload.customer.tax_id,
            customer_tax_system=payload.customer.tax_regime,
            customer_zip=payload.customer.postal_code,
            use=payload.customer.cfdi_use,
            payment_form=payload.charge.payment_form,
            payment_method=payload.charge.payment_method,
            line_items=line_items,
            currency=payload.charge.currency,
            notes=f"Eva billing source={payload.source.type}",
        )
        factura = await self._create_pending_factura(db, factura_data)
        record = existing or EvaBillingRecord(
            account_id=payload.account_id,
            source_type=payload.source.type,
            idempotency_key=payload.idempotency_key,
        )
        record.stripe_invoice_id = payload.source.stripe_invoice_id
        record.stripe_payment_intent_id = payload.source.stripe_payment_intent_id
        record.stripe_subscription_id = payload.source.stripe_subscription_id
        record.stripe_customer_id = payload.source.stripe_customer_id
        record.stripe_charge_id = payload.source.stripe_charge_id
        record.factura_id = factura.id
        # The outbox worker will transition this to 'issued' (and then
        # 'email_sent' after successfully emailing the CFDI).
        record.status = "pending_stamp"
        record.recipient_email = recipient_emails[0] if recipient_emails else None
        record.currency = payload.charge.currency.upper()
        record.subtotal = _minor_to_major(quote.base_subtotal_minor)
        record.tax = _minor_to_major(quote.iva_minor)
        record.isr_retention = _minor_to_major(quote.isr_retention_minor)
        record.iva_retention = _minor_to_major(quote.iva_retention_minor)
        record.cedular_retention = _minor_to_major(quote.cedular_retention_minor) if quote.cedular_retention_minor else None
        record.total = _minor_to_major(quote.payable_total_minor)
        record.metadata_json = {
            "description": payload.charge.description,
            "retention_applicable": payload.charge.retention_applicable,
            "recipient_emails": recipient_emails,
            "cedular_retention_minor": quote.cedular_retention_minor,
            "cedular_state_code": quote.cedular_state_code,
            "cedular_rate": str(quote.cedular_rate) if quote.cedular_rate is not None else None,
            # Snapshot the customer block so the outbox worker can send
            # the invoice email after stamping without needing to re-fetch
            # the empresa (which could have been edited by then).
            "customer_legal_name": payload.customer.legal_name,
            "customer_tax_id": payload.customer.tax_id,
            "customer_tax_regime": payload.customer.tax_regime,
            "customer_postal_code": payload.customer.postal_code,
            "customer_cfdi_use": payload.customer.cfdi_use,
            "customer_person_type": payload.customer.person_type,
        }
        db.add(record)
        await db.flush()
        # Email is sent by the outbox worker AFTER stamping succeeds. Keeping
        # email out of this critical path is what lets us keep the webhook
        # response fast + ensures we never email a recipient about a CFDI
        # that ended up not being stamped.
        return EvaBillingStampResponse(
            status=record.status,
            factura_id=factura.id,
            cfdi_uuid=factura.cfdi_uuid,  # None until worker stamps
            pdf_url=factura.pdf_url,
            xml_url=factura.xml_url,
            email_status=record.email_status,
        )

    async def refund(self, db: AsyncSession, payload: EvaBillingRefundRequest) -> EvaBillingStampResponse:
        record = await db.scalar(
            select(EvaBillingRecord)
            .where(EvaBillingRecord.account_id == payload.account_id)
            .where(
                or_(
                    EvaBillingRecord.stripe_invoice_id == payload.stripe_invoice_id,
                    EvaBillingRecord.stripe_payment_intent_id == payload.stripe_payment_intent_id,
                    EvaBillingRecord.stripe_charge_id == payload.stripe_charge_id,
                    EvaBillingRecord.idempotency_key == payload.idempotency_key,
                )
            )
            .order_by(EvaBillingRecord.created_at.desc())
        )
        if not record or not record.factura_id:
            raise ValueError("Original invoice record not found")
        factura = await db.get(Factura, record.factura_id)
        if not factura or not factura.facturapi_id:
            raise ValueError("Original factura is missing")
        response_factura = factura
        if payload.refund_amount_minor >= payload.original_total_minor:
            response = await facturapi.cancel_invoice(factura.facturapi_id, motive="03")
            factura.status = "cancelled"
            factura.cancellation_status = response.get("cancellation_status") or response.get("status")
            record.status = "canceled"
        else:
            egreso_payload = {
                "type": "E",
                "customer": {
                    "legal_name": factura.customer_name,
                    "tax_id": factura.customer_rfc,
                    "tax_system": factura.customer_tax_system,
                    "address": {"zip": factura.customer_zip},
                },
                "payment_form": factura.payment_form,
                "payment_method": factura.payment_method,
                "use": factura.use,
                "items": [
                    {
                        "product": {
                            "description": f"Nota de credito EvaAI - {factura.customer_name}",
                            "product_key": SERVICE_PRODUCT_KEY,
                            "price": float(_minor_to_major(payload.refund_amount_minor)),
                            "tax_included": False,
                            "taxes": [{"type": "IVA", "rate": float(IVA_RATE)}],
                        }
                    }
                ],
                "related_documents": [{"relationship": "01", "documents": [factura.cfdi_uuid]}] if factura.cfdi_uuid else [],
            }
            api_result = await facturapi.create_egreso_invoice(egreso_payload)
            egreso = Factura(
                facturapi_id=api_result.get("id"),
                cfdi_uuid=api_result.get("uuid"),
                customer_name=factura.customer_name,
                customer_rfc=factura.customer_rfc,
                customer_id=factura.customer_id,
                account_id=factura.account_id,
                customer_tax_system=factura.customer_tax_system,
                customer_zip=factura.customer_zip,
                use=factura.use,
                payment_form=factura.payment_form,
                payment_method=factura.payment_method,
                line_items_json=[{"product_key": SERVICE_PRODUCT_KEY, "description": "Nota de credito EvaAI", "quantity": 1, "unit_price": float(_minor_to_major(payload.refund_amount_minor)), "tax_rate": float(IVA_RATE)}],
                subtotal=_minor_to_major(payload.refund_amount_minor),
                tax=Decimal("0.00"),
                isr_retention=Decimal("0.00"),
                iva_retention=Decimal("0.00"),
                total=_minor_to_major(payload.refund_amount_minor),
                currency=payload.currency.upper(),
                status=api_result.get("status", "valid"),
                notes=f"Egreso Eva billing linked to factura {factura.id}",
                pdf_url=api_result.get("pdf_custom_section"),
                xml_url=api_result.get("xml"),
                series=api_result.get("series"),
                folio_number=api_result.get("folio_number"),
                issued_at=datetime.now(timezone.utc),
            )
            db.add(egreso)
            await db.flush()
            record.status = "refund_issued"
            response_factura = egreso
        db.add(record)
        db.add(factura)
        await db.flush()
        return EvaBillingStampResponse(
            status=record.status,
            factura_id=response_factura.id,
            cfdi_uuid=response_factura.cfdi_uuid,
            pdf_url=response_factura.pdf_url,
            xml_url=response_factura.xml_url,
            email_status=record.email_status,
        )

    async def status(self, db: AsyncSession, account_id) -> EvaBillingStatusResponse:
        result = await db.execute(
            select(EvaBillingRecord)
            .where(EvaBillingRecord.account_id == account_id)
            .order_by(EvaBillingRecord.created_at.desc())
            .limit(20)
        )
        rows = list(result.scalars().all())
        items: list[EvaBillingStatusItem] = []
        for row in rows:
            factura = await db.get(Factura, row.factura_id) if row.factura_id else None
            items.append(
                EvaBillingStatusItem(
                    record_id=row.id,
                    status=row.status,
                    factura_id=row.factura_id,
                    cfdi_uuid=factura.cfdi_uuid if factura else None,
                    email_status=row.email_status,
                    total=row.total,
                    currency=row.currency,
                )
            )
        return EvaBillingStatusResponse(account_id=account_id, items=items)

    async def resend_invoice_email(self, db: AsyncSession, *, account_id, cfdi_uuid: str) -> EvaBillingStampResponse:
        result = await db.execute(
            select(EvaBillingRecord, Factura)
            .join(Factura, EvaBillingRecord.factura_id == Factura.id)
            .where(EvaBillingRecord.account_id == account_id)
            .where(Factura.cfdi_uuid == cfdi_uuid)
            .order_by(EvaBillingRecord.created_at.desc())
        )
        row = result.first()
        if not row:
            raise ValueError("Invoice record not found")
        record, factura = row
        if not record.recipient_email:
            raise ValueError("Invoice recipient email is missing")
        if not factura:
            raise ValueError("Factura is missing")
        recipient_emails = record.metadata_json.get("recipient_emails") if isinstance(record.metadata_json, dict) else None
        if not isinstance(recipient_emails, list):
            recipient_emails = [record.recipient_email]

        email_status, email_error = await self._send_invoice_email(
            recipient_emails=[email for email in recipient_emails if isinstance(email, str)],
            customer=EvaBillingCustomer(
                legal_name=factura.customer_name,
                tax_id=factura.customer_rfc,
                tax_regime=factura.customer_tax_system or "",
                postal_code=factura.customer_zip or "",
                cfdi_use=factura.use or "",
                person_type="persona_moral",
            ),
            factura=factura,
            total=factura.total or Decimal("0.00"),
        )
        record.email_status = email_status
        record.email_error = email_error
        if email_status == "sent":
            record.email_sent_at = datetime.now(timezone.utc)
            record.status = "email_sent"
        db.add(record)
        await db.flush()
        return EvaBillingStampResponse(
            status=record.status,
            factura_id=factura.id,
            cfdi_uuid=factura.cfdi_uuid,
            pdf_url=factura.pdf_url,
            xml_url=factura.xml_url,
            email_status=record.email_status,
        )

    async def _find_existing_record(self, db: AsyncSession, payload: EvaBillingStampRequest) -> EvaBillingRecord | None:
        return await db.scalar(
            select(EvaBillingRecord)
            .where(
                or_(
                    EvaBillingRecord.idempotency_key == payload.idempotency_key,
                    EvaBillingRecord.stripe_invoice_id == payload.source.stripe_invoice_id,
                    EvaBillingRecord.stripe_payment_intent_id == payload.source.stripe_payment_intent_id,
                )
            )
            .order_by(EvaBillingRecord.created_at.desc())
            .limit(1)
        )

    async def _create_pending_factura(self, db: AsyncSession, data: FacturaCreate) -> Factura:
        """Insert a factura row in ``status='pending_stamp'`` with a stable
        ``facturapi_idempotency_key``. The outbox worker (see
        ``src/facturas/outbox.py``) picks it up on the next cycle and calls
        FacturAPI. This replaces the old ``_create_and_stamp_factura`` which
        called FacturAPI synchronously and was vulnerable to the F-4
        data-loss pattern (stamp succeeds, commit fails, CFDI orphaned).
        """
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        isr_ret_total = Decimal("0.00")
        iva_ret_total = Decimal("0.00")
        cedular_total = Decimal("0.00")
        cedular_state: str | None = None
        cedular_rate_seen: Decimal | None = None
        line_items_store = []
        for li in data.line_items:
            line_sub = li.unit_price * li.quantity
            line_tax = line_sub * li.tax_rate
            subtotal += line_sub
            tax_total += line_tax
            if li.isr_retention:
                isr_ret_total += line_sub * li.isr_retention
            if li.iva_retention:
                iva_ret_total += line_sub * li.iva_retention
            if li.cedular_rate:
                cedular_total += line_sub * li.cedular_rate
                cedular_rate_seen = li.cedular_rate
                # Derive the state code from the customer's ZIP (authoritative
                # source — never from the free-form label, which could be
                # localized/reworded and silently mis-persist the state).
                if cedular_state is None:
                    cedular_state = state_from_zip(data.customer_zip)
            line_items_store.append(
                {
                    "product_key": li.product_key,
                    "description": li.description,
                    "quantity": li.quantity,
                    "unit_price": float(li.unit_price),
                    "tax_rate": float(li.tax_rate),
                    "isr_retention": float(li.isr_retention) if li.isr_retention else None,
                    "iva_retention": float(li.iva_retention) if li.iva_retention else None,
                    "cedular_rate": float(li.cedular_rate) if li.cedular_rate else None,
                    "cedular_label": li.cedular_label,
                }
            )
        factura = Factura(
            facturapi_id=None,
            customer_name=data.customer_name or "",
            customer_rfc=data.customer_rfc or "",
            customer_id=data.customer_id,
            account_id=data.account_id,
            customer_tax_system=data.customer_tax_system,
            customer_zip=data.customer_zip,
            use=data.use,
            payment_form=data.payment_form,
            payment_method=data.payment_method,
            line_items_json=line_items_store,
            subtotal=round(subtotal, 2),
            tax=round(tax_total, 2),
            isr_retention=round(isr_ret_total, 2),
            iva_retention=round(iva_ret_total, 2),
            local_retention=round(cedular_total, 2),
            local_retention_state=cedular_state,
            local_retention_rate=cedular_rate_seen,
            total=round(subtotal + tax_total - isr_ret_total - iva_ret_total - cedular_total, 2),
            currency=data.currency,
            status="pending_stamp",
            notes=data.notes,
            issued_at=None,
            created_by=None,
            stamp_retry_count=0,
        )
        db.add(factura)
        await db.flush()  # populates factura.id via uuid4 default
        factura.facturapi_idempotency_key = str(factura.id)
        await db.flush()
        return factura

    async def _send_invoice_email(
        self,
        *,
        recipient_emails: list[str],
        customer: EvaBillingCustomer,
        factura: Factura,
        total: Decimal,
    ) -> tuple[str, str | None]:
        api_key = (settings.sendgrid_api_key or "").strip()
        if not api_key:
            return "failed", "SendGrid not configured"
        if not recipient_emails:
            return "failed", "Invoice recipient email is missing"

        uuid_short = (factura.cfdi_uuid or "factura")[:8]
        html = (
            f"<p>Hola,</p>"
            f"<p>Tu factura de EvaAI ya fue emitida.</p>"
            f"<p><strong>Cliente:</strong> {customer.legal_name}<br/>"
            f"<strong>RFC:</strong> {customer.tax_id}<br/>"
            f"<strong>UUID:</strong> {factura.cfdi_uuid or 'pendiente'}<br/>"
            f"<strong>Total:</strong> {total} MXN</p>"
            f"<p>Los archivos PDF y XML de tu factura se encuentran adjuntos a este correo.</p>"
        )
        payload: dict = {
            "personalizations": [{"to": [{"email": email}]} for email in recipient_emails],
            "from": {
                "email": settings.billing_invoice_from_email,
                "name": settings.billing_invoice_from_name,
            },
            "reply_to": {"email": settings.sendgrid_reply_to},
            "subject": "Tu factura de EvaAI",
            "content": [{"type": "text/html", "value": html}],
        }

        attachments = await self._download_invoice_attachments(factura, uuid_short)
        if attachments:
            payload["attachments"] = attachments

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if response.status_code in {200, 202}:
                return "sent", None
            return "failed", f"SendGrid status {response.status_code}"
        except Exception as exc:  # pragma: no cover - defensive
            return "failed", str(exc)

    @staticmethod
    async def _download_invoice_attachments(
        factura: "Factura", uuid_short: str
    ) -> list[dict]:
        """Fetch the PDF and XML for a Facturapi invoice as base64 attachments.

        Failures are logged at WARNING (with the HTTP status / exception)
        rather than swallowed silently — historically the silent fallback
        sent invoices without attachments and we only noticed when a
        customer complained. Email is still sent without the missing
        attachment so the customer at least gets the notification.
        """
        import base64

        facturapi_id = getattr(factura, "facturapi_id", None)
        if not facturapi_id:
            logger.warning(
                "Cannot attach CFDI files: factura has no facturapi_id",
                extra={"cfdi_uuid": getattr(factura, "cfdi_uuid", None)},
            )
            return []

        api_key = (settings.facturapi_api_key or "").strip()
        if not api_key:
            logger.warning(
                "Cannot attach CFDI files: FACTURAPI_API_KEY is not configured",
                extra={"facturapi_id": facturapi_id},
            )
            return []

        attachments: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for ext, mime in [("pdf", "application/pdf"), ("xml", "application/xml")]:
                try:
                    resp = await client.get(
                        f"https://www.facturapi.io/v2/invoices/{facturapi_id}/{ext}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        follow_redirects=True,
                    )
                except Exception:
                    logger.warning(
                        "Failed to download CFDI %s from Facturapi (network/transport error) — "
                        "email will be sent without this attachment",
                        ext,
                        extra={"facturapi_id": facturapi_id},
                        exc_info=True,
                    )
                    continue
                if resp.status_code == 200:
                    attachments.append({
                        "content": base64.b64encode(resp.content).decode("ascii"),
                        "type": mime,
                        "filename": f"factura-{uuid_short}.{ext}",
                        "disposition": "attachment",
                    })
                else:
                    logger.warning(
                        "Facturapi returned HTTP %s when downloading CFDI %s — "
                        "email will be sent without this attachment",
                        resp.status_code, ext,
                        extra={"facturapi_id": facturapi_id, "body_preview": resp.text[:200]},
                    )
        return attachments


def compute_hmac_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def parse_json_body(raw_body: bytes) -> dict:
    return json.loads(raw_body.decode("utf-8"))
