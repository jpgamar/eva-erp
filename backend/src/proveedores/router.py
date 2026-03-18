import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.proveedores.models import Proveedor
from src.proveedores.schemas import ProveedorCreate, ProveedorResponse, ProveedorUpdate

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get("", response_model=list[ProveedorResponse])
async def list_proveedores(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Proveedor).order_by(Proveedor.name)
    if search:
        q = q.where(Proveedor.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ProveedorResponse, status_code=201)
async def create_proveedor(
    data: ProveedorCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proveedor = Proveedor(**data.model_dump())
    db.add(proveedor)
    await db.flush()
    await db.refresh(proveedor)
    return proveedor


@router.get("/{proveedor_id}", response_model=ProveedorResponse)
async def get_proveedor(
    proveedor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Proveedor).where(Proveedor.id == proveedor_id))
    proveedor = result.scalar_one_or_none()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor not found")
    return proveedor


@router.patch("/{proveedor_id}", response_model=ProveedorResponse)
async def update_proveedor(
    proveedor_id: uuid.UUID,
    data: ProveedorUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Proveedor).where(Proveedor.id == proveedor_id))
    proveedor = result.scalar_one_or_none()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(proveedor, field, value)
    db.add(proveedor)
    return proveedor


@router.delete("/{proveedor_id}", status_code=204)
async def delete_proveedor(
    proveedor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Proveedor).where(Proveedor.id == proveedor_id))
    proveedor = result.scalar_one_or_none()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor not found")
    await db.delete(proveedor)
