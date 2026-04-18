"""Outbox worker that timbres pending facturas with FacturAPI + retries.

Design
------
The flow avoids the F-4 data-loss class of bugs:

    Caller path                  Worker path (this file)
    ──────────                   ────────────────────────
    INSERT factura               SELECT FOR UPDATE SKIP LOCKED
      status='pending_stamp'       WHERE status='pending_stamp'
      idempotency_key=str(id)      AND (next_retry_at IS NULL
    COMMIT                             OR next_retry_at <= now())
    return 202 to client         ────────────
                                 POST /v2/invoices
                                   body.idempotency_key=<key>
                                 on success:
                                   UPDATE factura set
                                     facturapi_id, cfdi_uuid,
                                     status='valid',
                                     pdf_url, xml_url, ...
                                   COMMIT
                                 on failure:
                                   bump retry counter, set next_retry_at
                                   COMMIT
                                   after N attempts → status='stamp_failed'
                                   + alert to billing_monitor

Because the caller commits the row BEFORE calling FacturAPI, there is no
window where a stamped CFDI could exist with no ERP record. And because
we pass ``idempotency_key`` on every attempt, if FacturAPI already stamped
the invoice but the worker crashed before recording the response, a retry
returns the same CFDI (replay-safe).

Backoff schedule
----------------
Retry attempt 1  → +30s
Retry attempt 2  → +2m
Retry attempt 3  → +10m
Retry attempt 4  → +1h
Retry attempt 5  → +6h
After 5 attempts → status='stamp_failed', human intervention needed.

Concurrency
-----------
The SELECT uses ``FOR UPDATE SKIP LOCKED`` so multiple worker instances
(if we ever run >1 replica) don't fight for the same row.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import async_session
from src.facturas import service as facturapi
from src.facturas.models import CfdiPayment, Factura
from src.facturas.schemas import FacturaCreate, FacturaLineItem

logger = logging.getLogger(__name__)


def _is_permanent_facturapi_error(exc: BaseException) -> bool:
    """Return True for errors the worker should NOT retry.

    ``facturas.service.create_invoice`` wraps FacturAPI 4xx responses as
    ``HTTPException(502, detail={'facturapi_error': ...})``. The upstream
    4xx itself is hidden inside the detail. For permanent-failure
    classification we look at the detail string for the well-known SAT /
    FacturAPI validation markers — anything matching those means the
    payload is broken and will fail identically on every retry, so we
    skip the backoff and go straight to ``stamp_failed`` for human
    intervention.

    Transient errors (5xx, timeout, network reset) default to retry.
    """
    if not isinstance(exc, HTTPException):
        return False
    detail = getattr(exc, "detail", "")
    detail_str = str(detail).lower() if detail else ""
    permanent_markers = (
        "tax_id",            # invalid RFC
        "rfc",               # invalid RFC (alternate wording)
        "invalid",           # generic "X is invalid"
        "validation",        # validation error
        "bad request",
        "unprocessable",
        "schema",
        "uso",               # uso de cfdi invalid
        "tax_system",        # regimen fiscal invalid
        "postal",            # postal code / zip invalid
    )
    return any(marker in detail_str for marker in permanent_markers)


# Backoff steps per retry attempt. Index 0 = first retry (after the initial
# failure), so after 5 failures we hit the end of the list.
_BACKOFF_SECONDS = (30, 120, 600, 3600, 21600)

_BATCH_SIZE = 10


def _next_retry_delay(retry_count: int) -> timedelta:
    """Return the delay before the next attempt, given how many retries have occurred."""
    idx = min(max(retry_count, 0), len(_BACKOFF_SECONDS) - 1)
    return timedelta(seconds=_BACKOFF_SECONDS[idx])


def _rebuild_factura_create(factura: Factura) -> FacturaCreate:
    """Rebuild a FacturaCreate from the stored Factura row so we can
    re-run ``build_facturapi_payload`` against it.
    """
    line_items = []
    for li in (factura.line_items_json or []):
        line_items.append(
            FacturaLineItem(
                product_key=li["product_key"],
                description=li["description"],
                quantity=li.get("quantity", 1),
                unit_price=Decimal(str(li["unit_price"])),
                tax_rate=Decimal(str(li.get("tax_rate", "0.16"))),
                isr_retention=Decimal(str(li["isr_retention"])) if li.get("isr_retention") else None,
                iva_retention=Decimal(str(li["iva_retention"])) if li.get("iva_retention") else None,
                cedular_rate=Decimal(str(li["cedular_rate"])) if li.get("cedular_rate") else None,
                cedular_label=li.get("cedular_label"),
            )
        )
    return FacturaCreate(
        customer_name=factura.customer_name,
        customer_rfc=factura.customer_rfc,
        customer_id=factura.customer_id,
        account_id=factura.account_id,
        customer_tax_system=factura.customer_tax_system,
        customer_zip=factura.customer_zip,
        use=factura.use,
        payment_form=factura.payment_form,
        payment_method=factura.payment_method,
        line_items=line_items,
        currency=factura.currency,
        notes=factura.notes,
    )


async def _apply_facturapi_success(factura: Factura, api_result: dict) -> None:
    """Populate factura with the CFDI data returned by FacturAPI."""
    factura.facturapi_id = api_result["id"]
    factura.cfdi_uuid = api_result.get("uuid")
    factura.status = api_result.get("status", "valid")
    factura.pdf_url = api_result.get("pdf_custom_section")
    factura.xml_url = api_result.get("xml")
    factura.series = api_result.get("series")
    factura.folio_number = api_result.get("folio_number")
    factura.issued_at = datetime.now(timezone.utc)
    factura.last_stamp_error = None
    factura.next_retry_at = None
    api_total = api_result.get("total")
    if api_total:
        factura.total = Decimal(str(api_total))


async def stamp_pending_factura(db: AsyncSession, factura: Factura) -> Factura:
    """Call FacturAPI for a single pending factura, mutating the row in place.

    Caller is responsible for committing. On success the row is marked
    ``status='valid'``; on failure retry bookkeeping is updated but no
    exception is raised (the worker decides whether to retry).
    """
    factura.stamp_attempted_at = datetime.now(timezone.utc)

    # idempotency_key is the row id — stable across retries, unique per row.
    # Stored durably before first stamp attempt so a crash recovery retry
    # sends the same key and gets the same CFDI back.
    key = factura.facturapi_idempotency_key
    if not key:
        key = str(factura.id)
        factura.facturapi_idempotency_key = key

    data = _rebuild_factura_create(factura)

    try:
        payload = facturapi.build_facturapi_payload(data, idempotency_key=key)
        api_result = await facturapi.create_invoice(payload)
    except Exception as exc:  # pragma: no cover - branching per error type below
        factura.stamp_retry_count = (factura.stamp_retry_count or 0) + 1
        factura.last_stamp_error = str(exc)[:2000]
        permanent = _is_permanent_facturapi_error(exc)
        if permanent or factura.stamp_retry_count >= settings.facturapi_outbox_max_retries:
            factura.status = "stamp_failed"
            factura.next_retry_at = None
            # Fire-and-forget alert so one row's failure doesn't block the worker loop.
            asyncio.create_task(_report_stamp_failed(factura))
        else:
            delay = _next_retry_delay(factura.stamp_retry_count - 1)
            factura.next_retry_at = datetime.now(timezone.utc) + delay
        logger.warning(
            "Outbox stamp %s failed for factura %s (attempt %s/%s, permanent=%s): %s",
            "PERMANENT" if permanent else "transient",
            factura.id,
            factura.stamp_retry_count,
            settings.facturapi_outbox_max_retries,
            permanent,
            exc,
        )
        return factura

    await _apply_facturapi_success(factura, api_result)
    logger.info(
        "Outbox stamped factura %s on attempt %s (cfdi_uuid=%s)",
        factura.id,
        (factura.stamp_retry_count or 0) + 1,
        factura.cfdi_uuid,
    )
    # If this factura was created by the Eva billing bridge (Stripe webhook
    # path), the linked EvaBillingRecord is still in status='pending_stamp'
    # and the customer hasn't been emailed. Finish the chain here so the
    # handoff is invisible to external callers.
    await _maybe_finalize_eva_billing_record(db, factura)
    return factura


async def _maybe_finalize_eva_billing_record(
    db: AsyncSession, factura: Factura
) -> None:
    """If an ``EvaBillingRecord`` points at this factura, send the invoice
    email and mark the record as ``issued`` / ``email_sent``.

    Called after ``stamp_pending_factura`` succeeds. Safe to call even when
    the factura was not created via the Eva billing bridge — the query
    simply returns None and nothing happens.

    Errors sending the email are logged but do not revert the factura's
    ``valid`` status. The email flow is best-effort; a missing invoice
    email is less bad than a missing CFDI.
    """
    from src.eva_billing.models import EvaBillingRecord
    from src.eva_billing.schemas import EvaBillingCustomer
    from src.eva_billing.service import EvaBillingService

    record = await db.scalar(
        select(EvaBillingRecord).where(EvaBillingRecord.factura_id == factura.id)
    )
    if record is None:
        return
    if record.status in {"email_sent", "issued"} and record.email_status == "sent":
        return  # already finalized on a previous pass

    # Customer snapshot stored by EvaBillingService.stamp when it enqueued
    # this row. We snapshot rather than re-fetch empresa so a late edit to
    # the empresa row can't silently change the email's customer block.
    meta = record.metadata_json or {}
    customer = EvaBillingCustomer(
        legal_name=meta.get("customer_legal_name") or factura.customer_name,
        tax_id=meta.get("customer_tax_id") or factura.customer_rfc,
        tax_regime=meta.get("customer_tax_regime") or (factura.customer_tax_system or ""),
        postal_code=meta.get("customer_postal_code") or (factura.customer_zip or ""),
        cfdi_use=meta.get("customer_cfdi_use") or (factura.use or ""),
        person_type=meta.get("customer_person_type") or "persona_moral",
    )
    recipient_emails = meta.get("recipient_emails") or []
    if not isinstance(recipient_emails, list):
        recipient_emails = []
    if not recipient_emails and record.recipient_email:
        recipient_emails = [record.recipient_email]

    svc = EvaBillingService()
    email_status, email_error = await svc._send_invoice_email(  # noqa: SLF001 - reuse of module-private helper
        recipient_emails=recipient_emails,
        customer=customer,
        factura=factura,
        total=factura.total or Decimal("0.00"),
    )
    record.email_status = email_status
    record.email_error = email_error
    if email_status == "sent":
        record.email_sent_at = datetime.now(timezone.utc)
        record.status = "email_sent"
    else:
        record.status = "issued"
        # Elevate to billing_monitor so an operator can resend manually.
        try:
            from src.eva_platform.billing_monitor import report_billing_issue

            await report_billing_issue(
                category="billing_email_failure",
                severity="high",
                title=f"Factura email failed: {customer.legal_name}",
                summary=f"factura={factura.id} error={email_error}",
                empresa_id=str(record.account_id) if record.account_id else None,
                empresa_name=customer.legal_name,
                stripe_invoice_id=record.stripe_invoice_id,
            )
        except Exception:
            logger.warning("Failed to report email failure to monitoring", exc_info=True)
    db.add(record)


async def _report_stamp_failed(factura: Factura) -> None:
    """Ping the billing monitor. Never raises — alerting must never block work."""
    try:
        from src.eva_platform.billing_monitor import report_billing_issue

        await report_billing_issue(
            category="billing_cfdi_failure",
            severity="critical",
            title=f"CFDI stamp failed after retries: {factura.customer_name}",
            summary=(
                f"factura={factura.id} customer={factura.customer_name} "
                f"rfc={factura.customer_rfc} total={factura.total} "
                f"retries={factura.stamp_retry_count} "
                f"last_error={(factura.last_stamp_error or '')[:500]}"
            ),
            empresa_id=str(factura.account_id) if factura.account_id else None,
            empresa_name=factura.customer_name,
        )
    except Exception:
        logger.exception("Failed to report stamp_failed for factura %s", factura.id)


def _rollback_payment_optimistic_bump(
    factura: Factura, payment: CfdiPayment, db: AsyncSession
) -> None:
    """Undo the ``factura.total_paid`` + ``payment_status`` bump that
    ``register_payment`` applied optimistically when the user registered
    the payment.

    Called when a complemento transitions to ``stamp_failed`` — at that
    point the cash never actually landed in the fiscal sense, so leaving
    the factura looking "partially paid" would block subsequent payment
    registrations with a false "exceeds outstanding balance" error.
    (Codex round-2 P1, 2026-04-18.)
    """
    from src.facturas.payment_complements import _derive_payment_status

    current_total = Decimal(str(factura.total_paid or 0))
    new_total = (current_total - Decimal(str(payment.payment_amount))).quantize(
        Decimal("0.01")
    )
    if new_total < Decimal("0"):
        new_total = Decimal("0")
    factura.total_paid = new_total
    factura.payment_status = _derive_payment_status(factura.total, new_total)
    db.add(factura)


async def stamp_pending_payment(db: AsyncSession, payment: CfdiPayment) -> CfdiPayment:
    """Stamp a single Complemento de Pago. Same contract as
    ``stamp_pending_factura``: mutate the row, don't commit here.

    Needs to fetch the related Factura to build the type P payload
    (customer block + original UUID reference).

    On permanent failure (``stamp_failed``) we roll back the optimistic
    ``factura.total_paid`` / ``payment_status`` bumps that
    ``payment_complements.register_payment`` applied. Without the
    rollback, subsequent payments against the same factura would hit a
    false "exceeds outstanding balance" error because total_paid would
    keep growing for complementos that never made it to SAT.
    (Codex round-2 P1, 2026-04-18.)
    """
    payment.stamp_attempted_at = datetime.now(timezone.utc)
    if not payment.facturapi_idempotency_key:
        payment.facturapi_idempotency_key = f"pago:{payment.id}"

    factura = await db.get(Factura, payment.factura_id)
    if factura is None or not factura.cfdi_uuid:
        # Can't stamp a complement without the original CFDI's UUID.
        payment.stamp_retry_count = (payment.stamp_retry_count or 0) + 1
        payment.last_stamp_error = (
            "Original factura missing or unstamped — cannot build complemento"
        )
        payment.status = "stamp_failed"
        payment.next_retry_at = None
        if factura is not None:
            _rollback_payment_optimistic_bump(factura, payment, db)
        return payment

    try:
        payload = facturapi.build_payment_complement_payload(
            factura=factura,
            payment=payment,
            idempotency_key=payment.facturapi_idempotency_key,
        )
        api_result = await facturapi.create_invoice(payload)
    except Exception as exc:
        payment.stamp_retry_count = (payment.stamp_retry_count or 0) + 1
        payment.last_stamp_error = str(exc)[:2000]
        permanent = _is_permanent_facturapi_error(exc)
        if permanent or payment.stamp_retry_count >= settings.facturapi_outbox_max_retries:
            payment.status = "stamp_failed"
            payment.next_retry_at = None
            _rollback_payment_optimistic_bump(factura, payment, db)
            asyncio.create_task(_report_payment_failed(factura, payment))
        else:
            delay = _next_retry_delay(payment.stamp_retry_count - 1)
            payment.next_retry_at = datetime.now(timezone.utc) + delay
        logger.warning(
            "Outbox complemento %s failed for payment %s (factura %s, attempt %s/%s, permanent=%s): %s",
            "PERMANENT" if permanent else "transient",
            payment.id,
            payment.factura_id,
            payment.stamp_retry_count,
            settings.facturapi_outbox_max_retries,
            permanent,
            exc,
        )
        return payment

    payment.facturapi_id = api_result["id"]
    payment.cfdi_uuid = api_result.get("uuid")
    payment.status = "valid"
    payment.pdf_url = api_result.get("pdf_custom_section")
    payment.xml_url = api_result.get("xml")
    payment.last_stamp_error = None
    payment.next_retry_at = None
    logger.info(
        "Outbox stamped complemento %s for factura %s (cfdi_uuid=%s)",
        payment.id,
        payment.factura_id,
        payment.cfdi_uuid,
    )
    return payment


async def _report_payment_failed(factura: Factura, payment: CfdiPayment) -> None:
    try:
        from src.eva_platform.billing_monitor import report_billing_issue

        await report_billing_issue(
            category="billing_cfdi_failure",
            severity="critical",
            title=f"Complemento de pago failed after retries: {factura.customer_name}",
            summary=(
                f"payment={payment.id} factura={factura.id} "
                f"amount={payment.payment_amount} payment_date={payment.payment_date} "
                f"retries={payment.stamp_retry_count} "
                f"last_error={(payment.last_stamp_error or '')[:500]}"
            ),
            empresa_id=str(factura.account_id) if factura.account_id else None,
            empresa_name=factura.customer_name,
        )
    except Exception:
        logger.exception(
            "Failed to report stamp_failed for payment %s", payment.id
        )


async def process_pending_facturas_once(db: AsyncSession) -> dict[str, int]:
    """One worker pass for both pending facturas AND pending payments.

    Facturas go first (a complement can't stamp before its original), then
    payments. Both use ``FOR UPDATE SKIP LOCKED`` so multiple workers
    (if we ever scale out) don't contend on the same row.
    """
    now = datetime.now(timezone.utc)

    fact_stmt = (
        select(Factura)
        .where(Factura.status == "pending_stamp")
        .where((Factura.next_retry_at.is_(None)) | (Factura.next_retry_at <= now))
        .order_by(Factura.next_retry_at.asc().nulls_first())
        .limit(_BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    fact_result = await db.execute(fact_stmt)
    pending_facturas = list(fact_result.scalars().all())

    # SAT 5-day rule for Complementos de Pago: oldest payment_date first
    # so near-deadline rows get priority even under backlog.
    pay_stmt = (
        select(CfdiPayment)
        .where(CfdiPayment.status == "pending_stamp")
        .where((CfdiPayment.next_retry_at.is_(None)) | (CfdiPayment.next_retry_at <= now))
        .order_by(
            CfdiPayment.payment_date.asc(),
            CfdiPayment.next_retry_at.asc().nulls_first(),
        )
        .limit(_BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    pay_result = await db.execute(pay_stmt)
    pending_payments = list(pay_result.scalars().all())

    stats = {
        "facturas_picked": len(pending_facturas),
        "facturas_stamped": 0,
        "facturas_retried": 0,
        "facturas_failed": 0,
        "payments_picked": len(pending_payments),
        "payments_stamped": 0,
        "payments_retried": 0,
        "payments_failed": 0,
    }

    for factura in pending_facturas:
        await stamp_pending_factura(db, factura)
        if factura.status == "valid":
            stats["facturas_stamped"] += 1
        elif factura.status == "stamp_failed":
            stats["facturas_failed"] += 1
        else:
            stats["facturas_retried"] += 1

    for payment in pending_payments:
        await stamp_pending_payment(db, payment)
        if payment.status == "valid":
            stats["payments_stamped"] += 1
        elif payment.status == "stamp_failed":
            stats["payments_failed"] += 1
        else:
            stats["payments_retried"] += 1

    if pending_facturas or pending_payments:
        await db.commit()
    return stats


async def run_outbox_once() -> dict[str, int]:
    """Session-managed single pass. Safe to call from a loop or manually."""
    if not settings.facturapi_outbox_enabled:
        return {"skipped": 1}
    if not (settings.facturapi_api_key or "").strip():
        logger.warning("Outbox worker: FACTURAPI_API_KEY not configured, skipping")
        return {"skipped": 1}

    async with async_session() as db:
        try:
            return await process_pending_facturas_once(db)
        except Exception:
            logger.exception("Outbox worker pass failed")
            try:
                await db.rollback()
            except Exception:
                pass
            return {"error": 1}


async def facturas_outbox_runner_loop(stop_event: asyncio.Event) -> None:
    """Background loop registered in main.py lifespan."""
    interval = max(int(settings.facturapi_outbox_interval_seconds), 5)
    logger.info("Outbox worker started (interval=%ss)", interval)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # stop_event was set → shutdown
        except asyncio.TimeoutError:
            stats = await run_outbox_once()
            if (stats.get("facturas_picked") or 0) + (stats.get("payments_picked") or 0) > 0:
                logger.info("Outbox pass: %s", stats)
    logger.info("Outbox worker stopped")
