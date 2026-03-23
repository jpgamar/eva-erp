from __future__ import annotations

import hmac
import logging
from uuid import UUID
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import get_db
from src.eva_billing.schemas import (
    EvaBillingQuoteRequest,
    EvaBillingQuoteResponse,
    EvaBillingRefundRequest,
    EvaBillingStampRequest,
    EvaBillingStampResponse,
    EvaBillingStatusResponse,
)
from src.eva_billing.service import EvaBillingService, compute_hmac_signature

router = APIRouter(prefix="/internal/eva-billing", tags=["eva-billing"])


async def require_eva_billing_auth(request: Request) -> None:
    secret = settings.eva_billing_bridge_secret.strip()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Eva billing bridge not configured")
    timestamp = request.headers.get("X-Eva-Billing-Timestamp")
    signature = request.headers.get("X-Eva-Billing-Signature")
    if not timestamp or not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing billing bridge signature")
    try:
        ts_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid billing bridge timestamp") from exc
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if abs(now_ts - ts_value) > settings.eva_billing_bridge_skew_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired billing bridge signature")
    raw_body = await request.body()
    expected = compute_hmac_signature(secret, timestamp, raw_body)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid billing bridge signature")


def get_service() -> EvaBillingService:
    return EvaBillingService()


@router.post("/quote", response_model=EvaBillingQuoteResponse, dependencies=[Depends(require_eva_billing_auth)])
async def quote(
    payload: EvaBillingQuoteRequest,
    service: EvaBillingService = Depends(get_service),
):
    return service.quote(payload)


@router.post("/stamp", response_model=EvaBillingStampResponse, dependencies=[Depends(require_eva_billing_auth)])
async def stamp(
    payload: EvaBillingStampRequest,
    db: AsyncSession = Depends(get_db),
    service: EvaBillingService = Depends(get_service),
):
    try:
        response = await service.stamp(db, payload)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in stamp endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refund", response_model=EvaBillingStampResponse, dependencies=[Depends(require_eva_billing_auth)])
async def refund(
    payload: EvaBillingRefundRequest,
    db: AsyncSession = Depends(get_db),
    service: EvaBillingService = Depends(get_service),
):
    try:
        response = await service.refund(db, payload)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/status/{account_id}", response_model=EvaBillingStatusResponse, dependencies=[Depends(require_eva_billing_auth)])
async def status_for_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: EvaBillingService = Depends(get_service),
):
    return await service.status(db, account_id)
