import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.pagos.models import PagoProveedor, PagoAplicacion
from src.pagos.schemas import (
    PagoApplyRequest,
    PagoAplicacionResponse,
    PagoProveedorCreate,
    PagoProveedorResponse,
    PagoProveedorSummary,
    PagoProveedorUpdate,
)
from src.facturas_proveedor.models import DiferenciaCambiaria, FacturaProveedor
from src.proveedores.models import Proveedor

router = APIRouter(prefix="/pagos", tags=["pagos"])

VALID_TIPOS = {"anticipo", "pago"}


async def _get_exchange_rate_for_date(db: AsyncSession, target_date: date) -> Decimal:
    """Get USD→MXN rate for a given date. Falls back to most recent."""
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
    # Fallback: get any rate
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


def _compute_base_mxn(amount: Decimal, currency: str, exchange_rate: Decimal) -> Decimal:
    if currency == "MXN":
        return amount
    return round(amount * exchange_rate, 2)


async def _enrich_pago(db: AsyncSession, pago: PagoProveedor) -> PagoProveedorResponse:
    """Build response dict with proveedor_name and applications."""
    prov = await db.execute(select(Proveedor.name).where(Proveedor.id == pago.proveedor_id))
    proveedor_name = prov.scalar_one_or_none()

    apps_result = await db.execute(
        select(PagoAplicacion)
        .where(PagoAplicacion.pago_id == pago.id)
        .order_by(PagoAplicacion.applied_at.desc())
    )
    applications = [PagoAplicacionResponse.model_validate(a) for a in apps_result.scalars().all()]

    return PagoProveedorResponse(
        id=pago.id,
        proveedor_id=pago.proveedor_id,
        proveedor_name=proveedor_name,
        tipo=pago.tipo,
        description=pago.description,
        amount=pago.amount,
        currency=pago.currency,
        exchange_rate=pago.exchange_rate,
        base_amount_mxn=pago.base_amount_mxn,
        payment_date=pago.payment_date,
        payment_method=pago.payment_method,
        reference=pago.reference,
        status=pago.status,
        applied_amount=pago.applied_amount,
        remaining_amount=pago.amount - pago.applied_amount,
        notes=pago.notes,
        applications=applications,
        created_at=pago.created_at,
        updated_at=pago.updated_at,
    )


@router.get("", response_model=list[PagoProveedorResponse])
async def list_pagos(
    proveedor_id: uuid.UUID | None = None,
    tipo: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(PagoProveedor).order_by(PagoProveedor.payment_date.desc())
    if proveedor_id:
        q = q.where(PagoProveedor.proveedor_id == proveedor_id)
    if tipo:
        q = q.where(PagoProveedor.tipo == tipo)
    if status:
        q = q.where(PagoProveedor.status == status)
    if start_date:
        q = q.where(PagoProveedor.payment_date >= start_date)
    if end_date:
        q = q.where(PagoProveedor.payment_date <= end_date)
    result = await db.execute(q)
    pagos = result.scalars().all()
    return [await _enrich_pago(db, p) for p in pagos]


@router.post("", response_model=PagoProveedorResponse, status_code=201)
async def create_pago(
    data: PagoProveedorCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.tipo not in VALID_TIPOS:
        raise HTTPException(status_code=400, detail=f"tipo must be one of: {', '.join(VALID_TIPOS)}")

    # Validate proveedor exists
    prov = await db.execute(select(Proveedor).where(Proveedor.id == data.proveedor_id))
    if not prov.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Proveedor not found")

    # Get or use provided exchange rate
    if data.exchange_rate:
        exchange_rate = data.exchange_rate
    elif data.currency == "MXN":
        exchange_rate = Decimal("1")
    else:
        exchange_rate = await _get_exchange_rate_for_date(db, data.payment_date)

    base_amount_mxn = _compute_base_mxn(data.amount, data.currency, exchange_rate)

    pago = PagoProveedor(
        proveedor_id=data.proveedor_id,
        tipo=data.tipo,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        exchange_rate=exchange_rate,
        base_amount_mxn=base_amount_mxn,
        payment_date=data.payment_date,
        payment_method=data.payment_method,
        reference=data.reference,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(pago)
    await db.flush()
    await db.refresh(pago)
    return await _enrich_pago(db, pago)


@router.get("/summary", response_model=PagoProveedorSummary)
async def pago_summary(
    tipo: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Build base filters
    pending_filter = PagoProveedor.status.in_(["pendiente", "parcial"])
    applied_filter = PagoProveedor.status == "aplicado"

    if tipo:
        pending_filter = pending_filter & (PagoProveedor.tipo == tipo)
        applied_filter = applied_filter & (PagoProveedor.tipo == tipo)

    # Pending pagos
    pending = await db.execute(
        select(
            func.coalesce(func.sum(PagoProveedor.amount - PagoProveedor.applied_amount), 0),
            func.coalesce(func.sum(PagoProveedor.base_amount_mxn - (PagoProveedor.applied_amount * PagoProveedor.exchange_rate)), 0),
            func.count(PagoProveedor.id),
        ).where(pending_filter)
    )
    pending_row = pending.one()

    # Applied pagos
    applied = await db.execute(
        select(
            func.coalesce(func.sum(PagoProveedor.applied_amount), 0),
            func.coalesce(func.sum(PagoProveedor.applied_amount * PagoProveedor.exchange_rate), 0),
            func.count(PagoProveedor.id),
        ).where(applied_filter)
    )
    applied_row = applied.one()

    # Total exchange differences from applications
    diff_q = select(func.coalesce(func.sum(PagoAplicacion.exchange_difference_mxn), 0))
    if tipo:
        diff_q = diff_q.join(PagoProveedor, PagoAplicacion.pago_id == PagoProveedor.id).where(PagoProveedor.tipo == tipo)
    diff_result = await db.execute(diff_q)
    total_diff = diff_result.scalar() or Decimal("0")

    return PagoProveedorSummary(
        total_pendiente_usd=pending_row[0],
        total_pendiente_mxn=pending_row[1],
        total_aplicado_usd=applied_row[0],
        total_aplicado_mxn=applied_row[1],
        total_diferencia_cambiaria_mxn=total_diff,
        count_pendientes=pending_row[2],
        count_aplicados=applied_row[2],
    )


@router.get("/{pago_id}", response_model=PagoProveedorResponse)
async def get_pago(
    pago_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(PagoProveedor).where(PagoProveedor.id == pago_id))
    pago = result.scalar_one_or_none()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago not found")
    return await _enrich_pago(db, pago)


@router.patch("/{pago_id}", response_model=PagoProveedorResponse)
async def update_pago(
    pago_id: uuid.UUID,
    data: PagoProveedorUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(PagoProveedor).where(PagoProveedor.id == pago_id))
    pago = result.scalar_one_or_none()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago not found")
    if pago.status != "pendiente":
        raise HTTPException(status_code=400, detail="Only pending pagos can be modified")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pago, field, value)

    # Recompute base amount if amount/currency/rate changed
    pago.base_amount_mxn = _compute_base_mxn(pago.amount, pago.currency, pago.exchange_rate)
    db.add(pago)
    return await _enrich_pago(db, pago)


@router.delete("/{pago_id}", status_code=204)
async def cancel_pago(
    pago_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(PagoProveedor).where(PagoProveedor.id == pago_id))
    pago = result.scalar_one_or_none()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago not found")
    if pago.status == "aplicado":
        raise HTTPException(status_code=400, detail="Cannot cancel a fully applied pago")
    pago.status = "cancelado"
    db.add(pago)


@router.post("/{pago_id}/apply", response_model=PagoAplicacionResponse)
async def apply_pago(
    pago_id: uuid.UUID,
    data: PagoApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Load pago
    result = await db.execute(select(PagoProveedor).where(PagoProveedor.id == pago_id))
    pago = result.scalar_one_or_none()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago not found")
    if pago.status in ("aplicado", "cancelado"):
        raise HTTPException(status_code=400, detail=f"Pago is {pago.status}")

    remaining = pago.amount - pago.applied_amount
    if data.amount > remaining:
        raise HTTPException(status_code=400, detail=f"Amount exceeds remaining ({remaining} {pago.currency})")

    # Load factura proveedor
    fp_result = await db.execute(select(FacturaProveedor).where(FacturaProveedor.id == data.factura_proveedor_id))
    factura = fp_result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura proveedor not found")
    if factura.status in ("pagada", "cancelada"):
        raise HTTPException(status_code=400, detail=f"Factura is {factura.status}")

    fp_remaining = factura.total - factura.paid_amount
    if data.amount > fp_remaining:
        raise HTTPException(status_code=400, detail=f"Amount exceeds factura remaining ({fp_remaining} {factura.currency})")

    # Compute exchange difference
    pago_rate = pago.exchange_rate
    document_rate = factura.exchange_rate
    base_at_pago = _compute_base_mxn(data.amount, pago.currency, pago_rate)
    base_at_document = _compute_base_mxn(data.amount, factura.currency, document_rate)
    # Positive = gain (pago was cheaper in MXN), Negative = loss
    exchange_diff = base_at_document - base_at_pago

    # Create application record
    application = PagoAplicacion(
        pago_id=pago.id,
        factura_proveedor_id=factura.id,
        applied_amount=data.amount,
        pago_rate=pago_rate,
        document_rate=document_rate,
        base_amount_at_pago_rate=base_at_pago,
        base_amount_at_document_rate=base_at_document,
        exchange_difference_mxn=exchange_diff,
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)

    # Update pago
    pago.applied_amount += data.amount
    if pago.applied_amount >= pago.amount:
        pago.status = "aplicado"
    else:
        pago.status = "parcial"
    db.add(pago)

    # Update factura proveedor
    factura.paid_amount += data.amount
    if factura.paid_amount >= factura.total:
        factura.status = "pagada"
    else:
        factura.status = "parcial"
    db.add(factura)

    # Record diferencia cambiaria
    if exchange_diff != 0:
        diff_record = DiferenciaCambiaria(
            source_type="pago_aplicacion",
            source_id=application.id,
            document_type="factura_proveedor",
            document_id=factura.id,
            proveedor_id=factura.proveedor_id,
            currency=pago.currency,
            foreign_amount=data.amount,
            original_rate=pago_rate,
            settlement_rate=document_rate,
            gain_loss_mxn=exchange_diff,
            period=factura.issue_date.strftime("%Y-%m"),
        )
        db.add(diff_record)

    await db.flush()
    await db.refresh(application)
    return application
