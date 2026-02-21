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
from src.facturas.models import Factura
from src.facturas.schemas import FacturaCreate, FacturaResponse
from src.facturas import service as facturapi

router = APIRouter(prefix="/facturas", tags=["facturas"])


def _build_facturapi_payload(data: FacturaCreate) -> dict:
    """Transform our schema into Facturapi's expected payload."""
    items = []
    for li in data.line_items:
        items.append({
            "product": {
                "description": li.description,
                "product_key": li.product_key,
                "price": float(li.unit_price),
                "tax_included": False,
                "taxes": [{"type": "IVA", "rate": float(li.tax_rate)}],
            },
            "quantity": li.quantity,
        })

    payload: dict = {
        "customer": {
            "legal_name": data.customer_name,
            "tax_id": data.customer_rfc,
            "tax_system": data.customer_tax_system,
            "address": {"zip": data.customer_zip},
        },
        "items": items,
        "use": data.use,
        "payment_form": data.payment_form,
        "payment_method": data.payment_method,
    }
    if data.notes:
        payload["comments"] = data.notes
    return payload


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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
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

    payload = _build_facturapi_payload(data)
    result = await facturapi.create_invoice(payload)

    # Calculate local totals from line items
    subtotal = Decimal(0)
    tax_total = Decimal(0)
    line_items_store = []
    for li in data.line_items:
        line_sub = li.unit_price * li.quantity
        line_tax = line_sub * li.tax_rate
        subtotal += line_sub
        tax_total += line_tax
        line_items_store.append({
            "product_key": li.product_key,
            "description": li.description,
            "quantity": li.quantity,
            "unit_price": float(li.unit_price),
            "tax_rate": float(li.tax_rate),
        })

    factura = Factura(
        facturapi_id=result["id"],
        cfdi_uuid=result.get("uuid"),
        customer_name=data.customer_name,
        customer_rfc=data.customer_rfc,
        customer_id=data.customer_id,
        use=data.use,
        payment_form=data.payment_form,
        payment_method=data.payment_method,
        line_items_json=line_items_store,
        subtotal=result.get("total", float(subtotal)) - result.get("tax", float(tax_total)),
        tax=result.get("tax", float(tax_total)),
        total=result.get("total", float(subtotal + tax_total)),
        currency=data.currency,
        status=result.get("status", "valid"),
        pdf_url=result.get("pdf_custom_section"),
        xml_url=result.get("xml"),
        series=result.get("series"),
        folio_number=result.get("folio_number"),
        issued_at=datetime.now(timezone.utc),
        created_by=user.id,
    )
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

    xml_bytes = await facturapi.download_xml(factura.facturapi_id)
    filename = f"CFDI_{factura.cfdi_uuid or factura.facturapi_id}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{factura_id}", response_model=FacturaResponse)
async def cancel_factura(
    factura_id: uuid.UUID,
    motive: str = "02",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Factura).where(Factura.id == factura_id))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    if factura.status == "cancelled":
        raise HTTPException(status_code=400, detail="Factura already cancelled")

    cancel_result = await facturapi.cancel_invoice(factura.facturapi_id, motive)
    factura.status = "cancelled"
    factura.cancellation_status = cancel_result.get("cancellation_status", "accepted")
    factura.cancelled_at = datetime.now(timezone.utc)
    db.add(factura)
    await db.flush()
    await db.refresh(factura)
    return factura
