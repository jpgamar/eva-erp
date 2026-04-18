"""Monthly declaración API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.declaracion.alerts import compute_alerts
from src.declaracion.schemas import DeclaracionAlertsResponse, DeclaracionResponse
from src.declaracion.service import compute_monthly_declaration

router = APIRouter(prefix="/declaracion", tags=["declaracion"])


@router.get("/alerts", response_model=DeclaracionAlertsResponse)
async def get_declaracion_alerts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dashboard alerts — pending complements, upcoming/overdue declaración,
    stamp failures. Computed on demand so they're always current.
    """
    return await compute_alerts(db)


# Today the ERP is single-tenant — the operator's RFC is static.
# When multi-tenancy arrives this moves to the empresa/user record.
_OPERATOR_RFC = "ZEPG070314VC1"


@router.get("/{year}/{month}", response_model=DeclaracionResponse)
async def get_monthly_declaration(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return ISR + IVA numbers for a given month.

    The values are the exact figures to type into the SAT portal under
    "ISR simplificado de confianza. Personas físicas" and "IVA
    simplificado de confianza". Also surfaces blocking warnings
    (pending payment complements, stamp failures) so the operator
    fixes them before presenting.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month must be 1-12")
    if year < 2020 or year > 2100:
        raise HTTPException(status_code=400, detail="unsupported year")
    return await compute_monthly_declaration(
        db, year=year, month=month, rfc=_OPERATOR_RFC
    )
