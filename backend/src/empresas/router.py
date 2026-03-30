import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Boolean, func, select, case, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.empresas.models import Empresa, EmpresaHistory, EmpresaItem
from src.empresas.schemas import (
    EmpresaCreate,
    EmpresaHistoryResponse,
    EmpresaItemCreate,
    EmpresaItemResponse,
    EmpresaItemUpdate,
    EmpresaResponse,
    EmpresaUpdate,
)

router = APIRouter(prefix="/empresas", tags=["empresas"])

TRACKED_FIELDS = {"status", "ball_on", "summary_note"}


@router.get("")
async def list_empresas(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        select(
            Empresa.id,
            Empresa.name,
            Empresa.logo_url,
            Empresa.status,
            Empresa.ball_on,
            Empresa.summary_note,
            Empresa.monthly_amount,
            Empresa.payment_day,
            Empresa.last_paid_date,
            func.count(EmpresaItem.id).label("item_count"),
            func.count(case((EmpresaItem.done == False, EmpresaItem.id))).label("pending_count"),
        )
        .outerjoin(EmpresaItem, EmpresaItem.empresa_id == Empresa.id)
        .group_by(Empresa.id)
        .order_by(Empresa.name)
    )
    if search:
        q = q.where(Empresa.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    rows = result.all()

    # Fetch pending items for all empresas in one query
    empresa_ids = [r.id for r in rows]
    pending_items_map: dict[uuid.UUID, list[dict]] = {eid: [] for eid in empresa_ids}

    if empresa_ids:
        items_q = (
            select(EmpresaItem.id, EmpresaItem.empresa_id, EmpresaItem.title)
            .where(EmpresaItem.empresa_id.in_(empresa_ids), EmpresaItem.done == False)
            .order_by(EmpresaItem.created_at.asc())
        )
        items_result = await db.execute(items_q)
        for item in items_result.all():
            pending_items_map[item.empresa_id].append({"id": str(item.id), "title": item.title})

    return [
        {
            "id": r.id,
            "name": r.name,
            "logo_url": r.logo_url,
            "status": r.status,
            "ball_on": r.ball_on,
            "summary_note": r.summary_note,
            "monthly_amount": float(r.monthly_amount) if r.monthly_amount is not None else None,
            "payment_day": r.payment_day,
            "last_paid_date": r.last_paid_date.isoformat() if r.last_paid_date else None,
            "item_count": r.item_count,
            "pending_count": r.pending_count,
            "pending_items": pending_items_map.get(r.id, []),
        }
        for r in rows
    ]


@router.post("", response_model=EmpresaResponse, status_code=201)
async def create_empresa(
    data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    empresa = Empresa(**data.model_dump(), created_by=user.id)
    db.add(empresa)
    await db.flush()
    await db.refresh(empresa, attribute_names=["items"])
    return empresa


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Empresa).where(Empresa.id == empresa_id).options(selectinload(Empresa.items))
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    return empresa


@router.patch("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: uuid.UUID,
    data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Empresa).where(Empresa.id == empresa_id).options(selectinload(Empresa.items))
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")

    update_data = data.model_dump(exclude_unset=True)

    # Record history for tracked fields
    for field in TRACKED_FIELDS:
        if field in update_data:
            old_value = getattr(empresa, field)
            new_value = update_data[field]
            if old_value != new_value:
                history = EmpresaHistory(
                    empresa_id=empresa.id,
                    field_changed=field,
                    old_value=str(old_value) if old_value is not None else None,
                    new_value=str(new_value) if new_value is not None else None,
                    changed_by=user.id,
                )
                db.add(history)

    for field, value in update_data.items():
        setattr(empresa, field, value)

    db.add(empresa)
    return empresa


@router.delete("/{empresa_id}", status_code=204)
async def delete_empresa(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    await db.delete(empresa)


# ── History ────────────────────────────────────────────────────────


@router.get("/{empresa_id}/history")
async def get_empresa_history(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify empresa exists
    result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")

    q = (
        select(
            EmpresaHistory.id,
            EmpresaHistory.field_changed,
            EmpresaHistory.old_value,
            EmpresaHistory.new_value,
            EmpresaHistory.changed_by,
            EmpresaHistory.changed_at,
            User.name.label("changed_by_name"),
        )
        .outerjoin(User, User.id == EmpresaHistory.changed_by)
        .where(EmpresaHistory.empresa_id == empresa_id)
        .order_by(EmpresaHistory.changed_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": r.id,
            "field_changed": r.field_changed,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "changed_by": r.changed_by,
            "changed_by_name": r.changed_by_name,
            "changed_at": r.changed_at,
        }
        for r in rows
    ]


# ── Items ──────────────────────────────────────────────────────────


@router.post("/{empresa_id}/items", response_model=EmpresaItemResponse, status_code=201)
async def create_item(
    empresa_id: uuid.UUID,
    data: EmpresaItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")

    item = EmpresaItem(
        empresa_id=empresa_id,
        title=data.title,
        created_by=user.id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=EmpresaItemResponse)
async def update_item(
    item_id: uuid.UUID,
    data: EmpresaItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}/toggle", response_model=EmpresaItemResponse)
async def toggle_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.done = not item.done
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
