"""Periodic FacturAPI → ERP reconciliation.

Two jobs:

1. **Adoption** — if somebody stamps a CFDI outside the ERP (directly
   from the FacturAPI dashboard, or a legacy script), this loop finds
   it and inserts a ``facturas`` row so the ERP's view of ingresos
   matches SAT's. This is how factura F-4 (2026-03-23 SERVIACERO)
   will enter the database on first run.

2. **Drift healing** — if the outbox worker called FacturAPI but the
   commit of the response failed, the row sits in ``pending_stamp``
   while FacturAPI already has a valid CFDI for that idempotency key.
   The next reconciliation pass detects this and promotes the row to
   ``valid`` with the FacturAPI data.

Mirror of ``finances.stripe_service.reconcile_stripe_events`` / ``run_nightly_stripe_reconciliation_once`` / ``stripe_reconciliation_runner_loop`` —
kept consistent so both loops use the same shutdown contract, config
naming, and logging style.

Triggering
----------
* Periodic loop (default every hour) registered in ``main.py`` lifespan.
* Manual endpoint ``POST /api/v1/facturas/reconcile`` for on-demand runs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import async_session
from src.facturas import service as facturapi
from src.facturas.models import Factura

logger = logging.getLogger(__name__)


_PAGE_SIZE = 50


async def _fetch_facturapi_page(page: int) -> dict:
    """GET one page of /v2/invoices. Returns the raw JSON response.

    Uses the live API key from settings. Callers are expected to handle
    the missing-key case before entering the loop.
    """
    url = f"{facturapi.FACTURAPI_BASE}/invoices"
    params = {"limit": _PAGE_SIZE, "page": page}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params, headers=facturapi._headers())
    resp.raise_for_status()
    return resp.json()


def _extract_facturapi_fields(inv: dict) -> dict:
    """Map a FacturAPI invoice JSON to our Factura columns.

    Kept in one place so the adopt + heal branches stay consistent, and
    so a FacturAPI schema change only has to be traced through one
    function instead of two.
    """
    customer = inv.get("customer") or {}
    # FacturAPI exposes items with product.price + quantity. We sum for subtotal.
    items = inv.get("items") or []
    subtotal_major = Decimal("0.00")
    tax_total = Decimal("0.00")
    isr_ret_total = Decimal("0.00")
    iva_ret_total = Decimal("0.00")
    local_ret_total = Decimal("0.00")
    line_items_store: list[dict] = []
    for it in items:
        product = it.get("product") or {}
        unit_price = Decimal(str(product.get("price") or 0))
        quantity = int(it.get("quantity") or 1)
        line_sub = unit_price * quantity
        subtotal_major += line_sub
        tax_rate = Decimal("0.16")  # default; overridden below if taxes include IVA
        isr_rate: Decimal | None = None
        iva_rate: Decimal | None = None
        for tax in (product.get("taxes") or []):
            rate = Decimal(str(tax.get("rate") or 0))
            if (tax.get("type") or "").upper() == "IVA" and not tax.get("withholding"):
                tax_rate = rate
                tax_total += line_sub * rate
            if (tax.get("type") or "").upper() == "ISR" and tax.get("withholding"):
                isr_rate = rate
                isr_ret_total += line_sub * rate
            if (tax.get("type") or "").upper() == "IVA" and tax.get("withholding"):
                iva_rate = rate
                iva_ret_total += line_sub * rate
        cedular_rate: Decimal | None = None
        cedular_label: str | None = None
        for local_tax in (product.get("local_taxes") or []):
            if local_tax.get("withholding"):
                cedular_rate = Decimal(str(local_tax.get("rate") or 0))
                cedular_label = local_tax.get("type")
                local_ret_total += line_sub * cedular_rate
        line_items_store.append(
            {
                "product_key": product.get("product_key"),
                "description": product.get("description"),
                "quantity": quantity,
                "unit_price": float(unit_price),
                "tax_rate": float(tax_rate),
                "isr_retention": float(isr_rate) if isr_rate else None,
                "iva_retention": float(iva_rate) if iva_rate else None,
                "cedular_rate": float(cedular_rate) if cedular_rate else None,
                "cedular_label": cedular_label,
            }
        )

    # FacturAPI status strings: 'valid', 'canceled', 'draft'. We normalize
    # 'canceled' → 'cancelled' to match the existing ERP convention.
    raw_status = (inv.get("status") or "valid").lower()
    status = "cancelled" if raw_status == "canceled" else raw_status

    issued_at_raw = inv.get("date")
    issued_at = None
    if issued_at_raw:
        # FacturAPI dates are ISO-8601 with optional "Z" suffix.
        issued_at = datetime.fromisoformat(issued_at_raw.replace("Z", "+00:00"))

    total = Decimal(str(inv.get("total") or 0))

    return {
        "facturapi_id": inv.get("id"),
        "cfdi_uuid": inv.get("uuid"),
        "customer_name": customer.get("legal_name") or "",
        "customer_rfc": customer.get("tax_id") or "",
        "customer_tax_system": customer.get("tax_system"),
        "customer_zip": (customer.get("address") or {}).get("zip"),
        "use": inv.get("use") or "G03",
        "payment_form": inv.get("payment_form") or "99",
        "payment_method": inv.get("payment_method") or "PUE",
        "line_items_json": line_items_store,
        "subtotal": round(subtotal_major, 2),
        "tax": round(tax_total, 2),
        "isr_retention": round(isr_ret_total, 2),
        "iva_retention": round(iva_ret_total, 2),
        "local_retention": round(local_ret_total, 2),
        "total": round(total, 2),
        "currency": inv.get("currency") or "MXN",
        "status": status,
        "series": inv.get("series"),
        "folio_number": inv.get("folio_number"),
        "issued_at": issued_at,
    }


async def _adopt_or_heal(db: AsyncSession, inv: dict, stats: dict) -> None:
    """Decide what to do for one FacturAPI invoice."""
    facturapi_id = inv.get("id")
    if not facturapi_id:
        stats["skipped"] += 1
        return

    existing = await db.scalar(
        select(Factura).where(Factura.facturapi_id == facturapi_id)
    )

    fields = _extract_facturapi_fields(inv)

    if existing is None:
        # Adopt: CFDI exists in FacturAPI but not in ERP DB.
        # This is how F-4 gets into the ERP on the first reconciliation run.
        factura = Factura(
            facturapi_id=fields["facturapi_id"],
            cfdi_uuid=fields["cfdi_uuid"],
            customer_name=fields["customer_name"],
            customer_rfc=fields["customer_rfc"],
            customer_tax_system=fields["customer_tax_system"],
            customer_zip=fields["customer_zip"],
            use=fields["use"],
            payment_form=fields["payment_form"],
            payment_method=fields["payment_method"],
            line_items_json=fields["line_items_json"],
            subtotal=fields["subtotal"],
            tax=fields["tax"],
            isr_retention=fields["isr_retention"],
            iva_retention=fields["iva_retention"],
            local_retention=fields["local_retention"],
            total=fields["total"],
            currency=fields["currency"],
            status=fields["status"],
            series=fields["series"],
            folio_number=fields["folio_number"],
            issued_at=fields["issued_at"],
            notes="Adopted from FacturAPI by reconciliation loop",
        )
        db.add(factura)
        stats["adopted"] += 1
        logger.info(
            "Reconciliation adopted CFDI %s (folio=%s, customer=%s, total=%s)",
            facturapi_id,
            fields["folio_number"],
            fields["customer_name"],
            fields["total"],
        )
        return

    # Heal: the row is in a bad state but FacturAPI has the truth.
    healed = False
    if existing.status in ("pending_stamp", "stamp_failed") and fields["status"] == "valid":
        existing.facturapi_id = fields["facturapi_id"]
        existing.cfdi_uuid = fields["cfdi_uuid"]
        existing.status = "valid"
        existing.pdf_url = existing.pdf_url or None
        existing.xml_url = existing.xml_url or None
        existing.series = fields["series"]
        existing.folio_number = fields["folio_number"]
        existing.issued_at = existing.issued_at or fields["issued_at"]
        existing.last_stamp_error = None
        existing.next_retry_at = None
        healed = True
        stats["healed"] += 1
        logger.info(
            "Reconciliation healed factura %s (was %s, now valid) — "
            "likely an outbox commit-after-stamp failure",
            existing.id,
            existing.status,
        )
    elif existing.status == "valid" and fields["status"] == "cancelled":
        existing.status = "cancelled"
        existing.cancelled_at = existing.cancelled_at or datetime.now(timezone.utc)
        healed = True
        stats["cancelled_synced"] += 1
        logger.info(
            "Reconciliation synced cancellation for factura %s (%s)",
            existing.id,
            existing.cfdi_uuid,
        )

    if not healed:
        stats["matched"] += 1


async def reconcile_facturapi_once(
    db: AsyncSession,
    *,
    max_invoices: int = 500,
) -> dict[str, int]:
    """One reconciliation pass. Returns stats dict.

    ``max_invoices`` caps the run so a backlog doesn't monopolize the
    event loop. Multiple passes will catch up over time.
    """
    stats = {
        "fetched": 0,
        "adopted": 0,
        "healed": 0,
        "cancelled_synced": 0,
        "matched": 0,
        "skipped": 0,
        "failed": 0,
    }
    page = 1
    processed = 0
    while processed < max_invoices:
        try:
            payload = await _fetch_facturapi_page(page)
        except Exception:
            logger.exception("Reconciliation: failed to fetch page %s", page)
            stats["failed"] += 1
            break
        data = payload.get("data") or []
        if not data:
            break
        for inv in data:
            try:
                await _adopt_or_heal(db, inv, stats)
            except Exception:
                logger.exception(
                    "Reconciliation: failed to adopt/heal CFDI %s",
                    inv.get("id"),
                )
                stats["failed"] += 1
            stats["fetched"] += 1
            processed += 1
            if processed >= max_invoices:
                break
        total_pages = int(payload.get("total_pages") or 1)
        if page >= total_pages:
            break
        page += 1
    return stats


async def run_facturapi_reconciliation_once() -> dict[str, int]:
    """Session-managed single pass. Safe to call from the loop or manually."""
    if not settings.facturapi_reconciliation_enabled:
        return {"skipped": 1}
    if not (settings.facturapi_api_key or "").strip():
        logger.warning(
            "Reconciliation: FACTURAPI_API_KEY not configured, skipping"
        )
        return {"skipped": 1}

    async with async_session() as db:
        try:
            stats = await reconcile_facturapi_once(db)
            await db.commit()
            logger.info("Reconciliation pass: %s", stats)
            return stats
        except Exception:
            logger.exception("Reconciliation pass failed")
            try:
                await db.rollback()
            except Exception:
                pass
            return {"error": 1}


async def facturapi_reconciliation_runner_loop(stop_event: asyncio.Event) -> None:
    """Background loop registered in main.py lifespan."""
    interval = max(int(settings.facturapi_reconciliation_interval_seconds), 300)
    logger.info("Reconciliation worker started (interval=%ss)", interval)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            await run_facturapi_reconciliation_once()
    logger.info("Reconciliation worker stopped")
