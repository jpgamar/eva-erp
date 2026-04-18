import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.config import settings
from src.common.database import get_db
from src.customers.models import Customer
from src.facturas import reconciliation as facturapi_reconciliation
from src.facturas.models import Factura
from src.facturas.schemas import FacturaCreate, FacturaLineItem, FacturaResponse
from src.facturas import service as facturapi

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.post("/reconcile")
async def trigger_reconciliation(
    max_invoices: int = 500,
    user: User = Depends(get_current_user),
) -> dict:
    """Trigger one reconciliation pass on demand.

    Normally the loop runs hourly (``facturapi_reconciliation_interval_seconds``).
    This endpoint is useful right after deploy (to adopt historical CFDIs
    like F-4) or when diagnosing drift.

    Each pass fetches up to ``max_invoices`` from FacturAPI and either
    ADOPTS them into ``facturas`` (if missing) or HEALS them (if the local
    row is ``pending_stamp``/``stamp_failed`` but the CFDI is already
    valid in FacturAPI). Returns a stats dict.
    """
    # Note: we deliberately create a fresh session in
    # run_facturapi_reconciliation_once so the endpoint handler's own
    # session doesn't hold a transaction open across potentially hundreds
    # of rows + HTTP calls. The caller gets back the stats synchronously.
    stats = await facturapi_reconciliation.run_facturapi_reconciliation_once()
    return {"max_invoices": max_invoices, "stats": stats}

@router.get("/api-status")
async def facturapi_status(user: User = Depends(get_current_user)):
    """Check if FacturAPI key is configured and reachable."""
    if not settings.facturapi_api_key:
        return {"status": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{facturapi.FACTURAPI_BASE}/invoices?limit=1",
                headers=facturapi._headers(),
            )
            if resp.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception:
        return {"status": "error", "detail": "Connection failed"}


@router.post("", response_model=FacturaResponse, status_code=201)
async def create_factura(
    data: FacturaCreate,
    draft: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a draft factura. With ?draft=true, push to Facturapi as draft (gets preview PDF).
    Without draft flag, stores locally only; stamp later via POST /facturas/{id}/stamp."""
    # If customer_id provided, look up customer and fill fiscal fields
    if data.customer_id:
        result = await db.execute(
            select(Customer).where(Customer.id == data.customer_id)
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        if not customer.legal_name or not customer.rfc:
            raise HTTPException(
                status_code=400,
                detail="Customer fiscal info incomplete — legal_name and rfc are required",
            )
        data.customer_name = customer.legal_name
        data.customer_rfc = customer.rfc
        data.customer_tax_system = customer.tax_regime
        data.customer_zip = customer.fiscal_zip
        if customer.default_cfdi_use:
            data.use = customer.default_cfdi_use
    else:
        # Manual entry — require customer_name and customer_rfc
        if not data.customer_name or not data.customer_rfc:
            raise HTTPException(
                status_code=400,
                detail="customer_name and customer_rfc are required when customer_id is not provided",
            )

    # Calculate local totals from line items
    subtotal = Decimal(0)
    tax_total = Decimal(0)
    isr_ret_total = Decimal(0)
    iva_ret_total = Decimal(0)
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
        line_items_store.append({
            "product_key": li.product_key,
            "description": li.description,
            "quantity": li.quantity,
            "unit_price": float(li.unit_price),
            "tax_rate": float(li.tax_rate),
            "isr_retention": float(li.isr_retention) if li.isr_retention else None,
            "iva_retention": float(li.iva_retention) if li.iva_retention else None,
        })

    facturapi_id: str | None = None
    total_amount = round(subtotal + tax_total - isr_ret_total - iva_ret_total, 2)
    if draft:
        payload = facturapi.build_facturapi_payload(data)
        api_result = await facturapi.create_draft_invoice(payload)
        facturapi_id = api_result.get("id")
        api_total = api_result.get("total")
        if api_total:
            total_amount = Decimal(str(api_total))

    factura = Factura(
        facturapi_id=facturapi_id,
        customer_name=data.customer_name,
        customer_rfc=data.customer_rfc,
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
        total=total_amount,
        currency=data.currency,
        status="draft",
        notes=data.notes,
        issued_at=None,
        created_by=user.id,
    )
    db.add(factura)
    await db.flush()
    await db.refresh(factura)
    return factura


@router.post("/{factura_id}/stamp", response_model=FacturaResponse, status_code=202)
async def stamp_factura(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enqueue a draft factura for async stamping via the outbox worker.

    The factura transitions ``draft → pending_stamp`` with a durable
    ``facturapi_idempotency_key``. The outbox worker (poll interval ~30s)
    picks it up and calls FacturAPI with the key, so a crash between
    "FacturAPI stamped" and "DB commit" cannot lose the CFDI — retry
    returns the same invoice.

    Returns 202 Accepted. Clients should poll ``GET /facturas/{id}`` until
    ``status='valid'`` (or ``stamp_failed`` after max retries).

    Historical note: this endpoint previously did a synchronous FacturAPI
    POST during the request handler, which exposed us to the F-4 data-loss
    bug (2026-04-18 incident) — a successful stamp followed by a DB commit
    failure silently lost the row. The outbox refactor eliminates that
    class of failure.
    """
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    if factura.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft facturas can be stamped")

    # If a draft was already pushed to FacturAPI (has facturapi_id), clear it —
    # the outbox worker will re-POST with a clean idempotency_key so we get a
    # fresh CFDI. The abandoned draft in FacturAPI is harmless (unstamped,
    # auto-expired). We intentionally do not delete it because doing so would
    # require an extra HTTP call inside this handler, reopening the atomicity
    # hole we're closing.
    factura.facturapi_id = None
    factura.cfdi_uuid = None

    factura.status = "pending_stamp"
    factura.facturapi_idempotency_key = str(factura.id)
    factura.stamp_retry_count = 0
    factura.last_stamp_error = None
    factura.next_retry_at = None
    factura.stamp_attempted_at = None

    db.add(factura)
    await db.flush()
    await db.refresh(factura)
    return factura


@router.get("", response_model=list[FacturaResponse])
async def list_facturas(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Factura).order_by(Factura.created_at.desc())
    if status:
        q = q.where(Factura.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{factura_id}", response_model=FacturaResponse)
async def get_factura(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    return factura


@router.get("/{factura_id}/pdf")
async def download_pdf(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    if not factura.facturapi_id:
        raise HTTPException(status_code=400, detail="Draft must be pushed to Facturapi first")

    pdf_bytes = await facturapi.download_pdf(factura.facturapi_id)
    filename = f"CFDI_{factura.cfdi_uuid or factura.facturapi_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{factura_id}/xml")
async def download_xml(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    if not factura.facturapi_id:
        raise HTTPException(status_code=400, detail="Draft facturas have no XML — stamp first")

    xml_bytes = await facturapi.download_xml(factura.facturapi_id)
    filename = f"CFDI_{factura.cfdi_uuid or factura.facturapi_id}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{factura_id}", response_model=FacturaResponse)
async def delete_or_cancel_factura(
    factura_id: uuid.UUID,
    motive: str = "02",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")

    if factura.status == "draft":
        # If pushed to Facturapi, remove the draft there too before hard-deleting locally.
        if factura.facturapi_id:
            await facturapi.delete_draft_invoice(factura.facturapi_id)
        await db.delete(factura)
        await db.flush()
        return Response(status_code=204)

    if factura.status == "cancelled":
        raise HTTPException(status_code=400, detail="Factura already cancelled")

    # Valid factura — SAT cancellation
    cancel_result = await facturapi.cancel_invoice(factura.facturapi_id, motive)
    factura.status = "cancelled"
    factura.cancellation_status = cancel_result.get("cancellation_status", "accepted")
    factura.cancelled_at = datetime.now(timezone.utc)
    db.add(factura)
    await db.flush()
    await db.refresh(factura)
    return factura
