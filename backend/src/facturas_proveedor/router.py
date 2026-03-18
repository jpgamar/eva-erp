import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.facturas_proveedor.models import DiferenciaCambiaria, FacturaProveedor
from src.facturas_proveedor.schemas import (
    DiferenciaCambiariaResponse,
    DiferenciaCambiariaSummary,
    FacturaProveedorCreate,
    FacturaProveedorResponse,
    FacturaProveedorUpdate,
)
from src.proveedores.models import Proveedor

router = APIRouter(prefix="/facturas-proveedor", tags=["facturas-proveedor"])
diferencias_router = APIRouter(prefix="/diferencias-cambiarias", tags=["diferencias-cambiarias"])


async def _get_exchange_rate_for_date(db: AsyncSession, target_date: date) -> Decimal:
    from src.finances.models import ExchangeRate

    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .where(ExchangeRate.effective_date <= target_date)
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if rate and rate.rate > 0:
        return rate.rate
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if rate and rate.rate > 0:
        return rate.rate
    raise HTTPException(status_code=400, detail="No exchange rate available. Please set one first.")


async def _enrich_factura(db: AsyncSession, fp: FacturaProveedor) -> FacturaProveedorResponse:
    prov = await db.execute(select(Proveedor.name).where(Proveedor.id == fp.proveedor_id))
    proveedor_name = prov.scalar_one_or_none()
    return FacturaProveedorResponse(
        id=fp.id,
        proveedor_id=fp.proveedor_id,
        proveedor_name=proveedor_name,
        invoice_number=fp.invoice_number,
        description=fp.description,
        subtotal=fp.subtotal,
        tax=fp.tax,
        total=fp.total,
        currency=fp.currency,
        exchange_rate=fp.exchange_rate,
        base_total_mxn=fp.base_total_mxn,
        status=fp.status,
        issue_date=fp.issue_date,
        due_date=fp.due_date,
        paid_amount=fp.paid_amount,
        remaining_amount=fp.total - fp.paid_amount,
        notes=fp.notes,
        pdf_url=fp.pdf_url,
        created_at=fp.created_at,
        updated_at=fp.updated_at,
    )


@router.get("", response_model=list[FacturaProveedorResponse])
async def list_facturas_proveedor(
    proveedor_id: uuid.UUID | None = None,
    status: str | None = None,
    currency: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(FacturaProveedor).order_by(FacturaProveedor.issue_date.desc())
    if proveedor_id:
        q = q.where(FacturaProveedor.proveedor_id == proveedor_id)
    if status:
        q = q.where(FacturaProveedor.status == status)
    if currency:
        q = q.where(FacturaProveedor.currency == currency)
    if start_date:
        q = q.where(FacturaProveedor.issue_date >= start_date)
    if end_date:
        q = q.where(FacturaProveedor.issue_date <= end_date)
    result = await db.execute(q)
    facturas = result.scalars().all()
    return [await _enrich_factura(db, fp) for fp in facturas]


@router.post("", response_model=FacturaProveedorResponse, status_code=201)
async def create_factura_proveedor(
    data: FacturaProveedorCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prov = await db.execute(select(Proveedor).where(Proveedor.id == data.proveedor_id))
    if not prov.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Proveedor not found")

    if data.exchange_rate:
        exchange_rate = data.exchange_rate
    elif data.currency == "MXN":
        exchange_rate = Decimal("1")
    else:
        exchange_rate = await _get_exchange_rate_for_date(db, data.issue_date)

    total = data.subtotal + data.tax
    base_total_mxn = total if data.currency == "MXN" else round(total * exchange_rate, 2)

    factura = FacturaProveedor(
        proveedor_id=data.proveedor_id,
        invoice_number=data.invoice_number,
        description=data.description,
        subtotal=data.subtotal,
        tax=data.tax,
        total=total,
        currency=data.currency,
        exchange_rate=exchange_rate,
        base_total_mxn=base_total_mxn,
        issue_date=data.issue_date,
        due_date=data.due_date,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(factura)
    await db.flush()
    await db.refresh(factura)
    return await _enrich_factura(db, factura)


@router.get("/{factura_id}", response_model=FacturaProveedorResponse)
async def get_factura_proveedor(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(FacturaProveedor).where(FacturaProveedor.id == factura_id))
    fp = result.scalar_one_or_none()
    if not fp:
        raise HTTPException(status_code=404, detail="Factura proveedor not found")
    return await _enrich_factura(db, fp)


@router.patch("/{factura_id}", response_model=FacturaProveedorResponse)
async def update_factura_proveedor(
    factura_id: uuid.UUID,
    data: FacturaProveedorUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(FacturaProveedor).where(FacturaProveedor.id == factura_id))
    fp = result.scalar_one_or_none()
    if not fp:
        raise HTTPException(status_code=404, detail="Factura proveedor not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fp, field, value)

    # Recompute total and base if subtotal/tax changed
    fp.total = fp.subtotal + fp.tax
    fp.base_total_mxn = fp.total if fp.currency == "MXN" else round(fp.total * fp.exchange_rate, 2)
    db.add(fp)
    return await _enrich_factura(db, fp)


@router.delete("/{factura_id}", status_code=204)
async def cancel_factura_proveedor(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(FacturaProveedor).where(FacturaProveedor.id == factura_id))
    fp = result.scalar_one_or_none()
    if not fp:
        raise HTTPException(status_code=404, detail="Factura proveedor not found")
    fp.status = "cancelada"
    db.add(fp)


@router.delete("/{factura_id}/hard", status_code=204)
async def hard_delete_factura_proveedor(
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Permanently delete a cancelled factura. Only works on cancelada status."""
    result = await db.execute(select(FacturaProveedor).where(FacturaProveedor.id == factura_id))
    fp = result.scalar_one_or_none()
    if not fp:
        raise HTTPException(status_code=404, detail="Factura proveedor not found")
    if fp.status != "cancelada":
        raise HTTPException(status_code=400, detail="Only cancelled facturas can be permanently deleted")
    await db.delete(fp)


# --- Diferencias Cambiarias ---

@diferencias_router.get("", response_model=list[DiferenciaCambiariaResponse])
async def list_diferencias(
    period: str | None = None,
    proveedor_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(DiferenciaCambiaria).order_by(DiferenciaCambiaria.created_at.desc())
    if period:
        q = q.where(DiferenciaCambiaria.period == period)
    if proveedor_id:
        q = q.where(DiferenciaCambiaria.proveedor_id == proveedor_id)
    if start_date:
        q = q.where(DiferenciaCambiaria.created_at >= start_date)
    if end_date:
        q = q.where(DiferenciaCambiaria.created_at <= end_date)
    result = await db.execute(q)
    diffs = result.scalars().all()

    enriched = []
    for d in diffs:
        prov_name = None
        if d.proveedor_id:
            prov = await db.execute(select(Proveedor.name).where(Proveedor.id == d.proveedor_id))
            prov_name = prov.scalar_one_or_none()
        enriched.append(DiferenciaCambiariaResponse(
            id=d.id,
            source_type=d.source_type,
            source_id=d.source_id,
            document_type=d.document_type,
            document_id=d.document_id,
            proveedor_id=d.proveedor_id,
            proveedor_name=prov_name,
            currency=d.currency,
            foreign_amount=d.foreign_amount,
            original_rate=d.original_rate,
            settlement_rate=d.settlement_rate,
            gain_loss_mxn=d.gain_loss_mxn,
            period=d.period,
            created_at=d.created_at,
        ))
    return enriched


@diferencias_router.get("/summary", response_model=DiferenciaCambiariaSummary)
async def diferencias_summary(
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(DiferenciaCambiaria)
    if year:
        q = q.where(DiferenciaCambiaria.period.like(f"{year}-%"))
    result = await db.execute(q)
    diffs = result.scalars().all()

    total_gain = Decimal("0")
    total_loss = Decimal("0")
    by_period: dict[str, Decimal] = {}

    for d in diffs:
        if d.gain_loss_mxn > 0:
            total_gain += d.gain_loss_mxn
        else:
            total_loss += d.gain_loss_mxn
        by_period[d.period] = by_period.get(d.period, Decimal("0")) + d.gain_loss_mxn

    return DiferenciaCambiariaSummary(
        total_gain_mxn=total_gain,
        total_loss_mxn=total_loss,
        net_mxn=total_gain + total_loss,
        count=len(diffs),
        by_period=by_period,
    )
