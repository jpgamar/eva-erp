import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.okrs.models import KeyResult, OKRPeriod, Objective
from src.okrs.schemas import (
    KeyResultCreate, KeyResultResponse, KeyResultUpdate,
    ObjectiveCreate, ObjectiveResponse, ObjectiveUpdate,
    PeriodCreate, PeriodResponse,
)

router = APIRouter(prefix="/okrs", tags=["okrs"])


def _calc_progress(start: Decimal, current: Decimal, target: Decimal) -> Decimal:
    if target == start:
        return Decimal("100") if current >= target else Decimal("0")
    pct = (current - start) / (target - start) * 100
    return max(Decimal("0"), min(Decimal("100"), round(pct, 2)))


@router.get("/active", response_model=PeriodResponse | None)
async def active_period(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OKRPeriod)
        .where(OKRPeriod.status == "active")
        .options(selectinload(OKRPeriod.objectives).selectinload(Objective.key_results))
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/periods", response_model=list[PeriodResponse])
async def list_periods(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OKRPeriod)
        .options(selectinload(OKRPeriod.objectives).selectinload(Objective.key_results))
        .order_by(OKRPeriod.start_date.desc())
    )
    return result.scalars().all()


@router.get("/periods/{period_id}", response_model=PeriodResponse)
async def get_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OKRPeriod)
        .where(OKRPeriod.id == period_id)
        .options(selectinload(OKRPeriod.objectives).selectinload(Objective.key_results))
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    return period


@router.post("/periods", response_model=PeriodResponse, status_code=201)
async def create_period(
    data: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    period = OKRPeriod(name=data.name, start_date=data.start_date, end_date=data.end_date, status=data.status)
    db.add(period)
    await db.flush()
    await db.refresh(period)
    return period


@router.post("/objectives", response_model=ObjectiveResponse, status_code=201)
async def create_objective(
    data: ObjectiveCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    obj = Objective(
        period_id=data.period_id, title=data.title, description=data.description,
        owner_id=data.owner_id, position=data.position,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


@router.patch("/objectives/{objective_id}", response_model=ObjectiveResponse)
async def update_objective(
    objective_id: uuid.UUID,
    data: ObjectiveUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Objective).where(Objective.id == objective_id)
        .options(selectinload(Objective.key_results))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.add(obj)
    return obj


@router.post("/key-results", response_model=KeyResultResponse, status_code=201)
async def create_key_result(
    data: KeyResultCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kr = KeyResult(
        objective_id=data.objective_id, title=data.title,
        target_value=data.target_value, unit=data.unit,
        tracking_mode=data.tracking_mode, auto_metric=data.auto_metric,
        start_value=data.start_value, current_value=data.start_value,
        progress_pct=Decimal("0"),
    )
    db.add(kr)
    await db.flush()
    await db.refresh(kr)
    return kr


@router.patch("/key-results/{kr_id}", response_model=KeyResultResponse)
async def update_key_result(
    kr_id: uuid.UUID,
    data: KeyResultUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(KeyResult).where(KeyResult.id == kr_id))
    kr = result.scalar_one_or_none()
    if not kr:
        raise HTTPException(status_code=404, detail="Key result not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(kr, field, value)

    kr.progress_pct = _calc_progress(kr.start_value, kr.current_value, kr.target_value)
    db.add(kr)
    return kr
