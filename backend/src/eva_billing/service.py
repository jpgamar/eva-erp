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


def _minor_to_major(amount_minor: int) -> Decimal:
    return (Decimal(amount_minor) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _major_to_minor(amount_major: Decimal) -> int:
    return int((amount_major * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _compute_quote(base_subtotal_minor: int, *, retention_applicable: bool) -> EvaBillingQuoteResponse:
    base_major = _minor_to_major(base_subtotal_minor)
    iva_major = (base_major * IVA_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    isr_major = Decimal("0.00")
    iva_ret_major = Decimal("0.00")
    if retention_applicable:
        isr_major = (base_major * ISR_RETENTION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        iva_ret_major = (base_major * IVA_RETENTION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_major = (base_major + iva_major - isr_major - iva_ret_major).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    payable_minor = _major_to_minor(total_major)
    iva_minor = _major_to_minor(iva_major)
    isr_minor = _major_to_minor(isr_major)
    iva_ret_minor = _major_to_minor(iva_ret_major)
    display_lines = [
        EvaBillingDisplayLine(label="Plan base", amount_minor=base_subtotal_minor),
        EvaBillingDisplayLine(label="IVA", amount_minor=iva_minor),
    ]
    if retention_applicable:
        display_lines.append(
            EvaBillingDisplayLine(label="Retenciones aplicables", amount_minor=-(isr_minor + iva_ret_minor))
        )
    display_lines.append(EvaBillingDisplayLine(label="Total a pagar", amount_minor=payable_minor))
    return EvaBillingQuoteResponse(
        retention_applicable=retention_applicable,
        currency="MXN",
        base_subtotal_minor=base_subtotal_minor,
        iva_minor=iva_minor,
        isr_retention_minor=isr_minor,
        iva_retention_minor=iva_ret_minor,
        payable_total_minor=payable_minor,
        display_lines=display_lines,
    )


class EvaBillingService:
    def quote(self, payload: EvaBillingQuoteRequest) -> EvaBillingQuoteResponse:
        retention_applicable = payload.customer.person_type == "persona_moral"
        return _compute_quote(payload.charge.base_subtotal_minor, retention_applicable=retention_applicable)

    async def stamp(self, db: AsyncSession, payload: EvaBillingStampRequest) -> EvaBillingStampResponse:
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

        quote = _compute_quote(payload.charge.base_subtotal_minor, retention_applicable=payload.charge.retention_applicable)
        if quote.payable_total_minor != payload.charge.payable_total_minor:
            raise ValueError("Quote total does not match Stripe payable amount")

        line_items = [
            FacturaLineItem(
                product_key=SERVICE_PRODUCT_KEY,
                description=payload.charge.description,
                quantity=1,
                unit_price=_minor_to_major(payload.charge.base_subtotal_minor),
                tax_rate=IVA_RATE,
                isr_retention=ISR_RETENTION_RATE if payload.charge.retention_applicable else None,
                iva_retention=IVA_RETENTION_RATE if payload.charge.retention_applicable else None,
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
        factura = await self._create_and_stamp_factura(db, factura_data)
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
        record.status = "issued"
        record.recipient_email = payload.owner_email
        record.currency = payload.charge.currency.upper()
        record.subtotal = _minor_to_major(quote.base_subtotal_minor)
        record.tax = _minor_to_major(quote.iva_minor)
        record.isr_retention = _minor_to_major(quote.isr_retention_minor)
        record.iva_retention = _minor_to_major(quote.iva_retention_minor)
        record.total = _minor_to_major(quote.payable_total_minor)
        record.metadata_json = {
            "description": payload.charge.description,
            "retention_applicable": payload.charge.retention_applicable,
        }
        db.add(record)
        await db.flush()
        record.email_status, record.email_error = await self._send_invoice_email(
            recipient_email=payload.owner_email,
            customer=payload.customer,
            factura=factura,
            total=_minor_to_major(quote.payable_total_minor),
        )
        if record.email_status == "sent":
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

        email_status, email_error = await self._send_invoice_email(
            recipient_email=record.recipient_email,
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
        )

    async def _create_and_stamp_factura(self, db: AsyncSession, data: FacturaCreate) -> Factura:
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        isr_ret_total = Decimal("0.00")
        iva_ret_total = Decimal("0.00")
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
            line_items_store.append(
                {
                    "product_key": li.product_key,
                    "description": li.description,
                    "quantity": li.quantity,
                    "unit_price": float(li.unit_price),
                    "tax_rate": float(li.tax_rate),
                    "isr_retention": float(li.isr_retention) if li.isr_retention else None,
                    "iva_retention": float(li.iva_retention) if li.iva_retention else None,
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
            total=round(subtotal + tax_total - isr_ret_total - iva_ret_total, 2),
            currency=data.currency,
            status="draft",
            notes=data.notes,
            issued_at=None,
            created_by=None,
        )
        db.add(factura)
        await db.flush()
        payload = facturapi.build_facturapi_payload(data)
        api_result = await facturapi.create_invoice(payload)
        api_total = Decimal(str(api_result.get("total", 0)))
        factura.facturapi_id = api_result["id"]
        factura.cfdi_uuid = api_result.get("uuid")
        factura.status = api_result.get("status", "valid")
        factura.pdf_url = api_result.get("pdf_custom_section")
        factura.xml_url = api_result.get("xml")
        factura.series = api_result.get("series")
        factura.folio_number = api_result.get("folio_number")
        factura.issued_at = datetime.now(timezone.utc)
        if api_total:
            factura.total = api_total
        db.add(factura)
        await db.flush()
        return factura

    async def _send_invoice_email(
        self,
        *,
        recipient_email: str,
        customer: EvaBillingCustomer,
        factura: Factura,
        total: Decimal,
    ) -> tuple[str, str | None]:
        api_key = (settings.sendgrid_api_key or "").strip()
        if not api_key:
            return "failed", "SendGrid not configured"
        html = (
            f"<p>Hola,</p>"
            f"<p>Tu factura de EvaAI ya fue emitida.</p>"
            f"<p><strong>Cliente:</strong> {customer.legal_name}<br/>"
            f"<strong>RFC:</strong> {customer.tax_id}<br/>"
            f"<strong>UUID:</strong> {factura.cfdi_uuid or 'pendiente'}<br/>"
            f"<strong>Total:</strong> {total} MXN</p>"
            f"<p>Puedes descargar tus archivos aqui:</p>"
            f"<p><a href='{factura.pdf_url or '#'}'>PDF</a> · <a href='{factura.xml_url or '#'}'>XML</a></p>"
        )
        payload = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {
                "email": settings.billing_invoice_from_email,
                "name": settings.billing_invoice_from_name,
            },
            "reply_to": {"email": settings.sendgrid_reply_to},
            "subject": "Tu factura de EvaAI",
            "content": [{"type": "text/html", "value": html}],
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
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


def compute_hmac_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def parse_json_body(raw_body: bytes) -> dict:
    return json.loads(raw_body.decode("utf-8"))
