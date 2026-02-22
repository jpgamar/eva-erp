"""Monitoring dashboard: live service checks + Eva monitoring tables."""

import asyncio
import uuid
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_eva_db, eva_engine
from src.eva_platform.models import EvaMonitoringCheck, EvaMonitoringIssue
from src.common.config import settings
from src.eva_platform.schemas import (
    MonitoringCheckResponse,
    MonitoringIssueResponse,
    MonitoringOverviewResponse,
    ServiceStatusItem,
    ServiceStatusResponse,
)


def _build_services() -> list[dict]:
    """Build service list with headers that may depend on runtime config."""
    return [
        {"name": "Backend API", "url": "https://api.goeva.ai/api/v1/health"},
        {"name": "Frontend", "url": "https://app.goeva.ai"},
        {"name": "ERP API", "url": "https://eva-erp-goevaai-30a99658.koyeb.app/health"},
        {"name": "WhatsApp", "url": "https://api.goeva.ai/api/v1/whatsapp/oauth/callback"},
        {
            "name": "Supabase Auth",
            "url": "https://emrkjhfxytpgxzejkhre.supabase.co/auth/v1/health",
            "headers": {"apikey": settings.supabase_service_role_key},
        },
    ]

router = APIRouter()


async def _check_service(client: httpx.AsyncClient, svc: dict) -> ServiceStatusItem:
    """Ping a service URL and return its status."""
    try:
        start = asyncio.get_event_loop().time()
        resp = await client.get(svc["url"], headers=svc.get("headers"), follow_redirects=True)
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        status = "up" if resp.status_code < 400 else "degraded" if resp.status_code < 500 else "down"
        return ServiceStatusItem(
            name=svc["name"], url=svc["url"], status=status,
            latency_ms=latency, http_status=resp.status_code,
        )
    except Exception as exc:
        return ServiceStatusItem(
            name=svc["name"], url=svc["url"], status="down",
            error=str(exc)[:200],
        )


async def _check_database() -> ServiceStatusItem:
    """Check Eva DB connectivity."""
    if not eva_engine:
        return ServiceStatusItem(name="Database", url="supabase", status="down", error="Not configured")
    try:
        start = asyncio.get_event_loop().time()
        async with eva_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceStatusItem(name="Database", url="supabase", status="up", latency_ms=latency)
    except Exception as exc:
        return ServiceStatusItem(name="Database", url="supabase", status="down", error=str(exc)[:200])


@router.get("/monitoring/services", response_model=ServiceStatusResponse)
async def service_status(user: User = Depends(get_current_user)):
    """Live health check of all Eva services."""
    services = _build_services()
    async with httpx.AsyncClient(timeout=8.0) as client:
        tasks = [_check_service(client, s) for s in services]
        tasks.append(_check_database())
        results = await asyncio.gather(*tasks)
    return ServiceStatusResponse(
        services=list(results),
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/monitoring/overview", response_model=MonitoringOverviewResponse)
async def monitoring_overview(
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    # Run counts
    critical = await eva_db.execute(
        select(func.count(EvaMonitoringIssue.id)).where(
            EvaMonitoringIssue.status.in_(["open", "acknowledged"]),
            EvaMonitoringIssue.severity == "critical",
        )
    )
    high = await eva_db.execute(
        select(func.count(EvaMonitoringIssue.id)).where(
            EvaMonitoringIssue.status.in_(["open", "acknowledged"]),
            EvaMonitoringIssue.severity == "high",
        )
    )
    total_open = await eva_db.execute(
        select(func.count(EvaMonitoringIssue.id)).where(
            EvaMonitoringIssue.status.in_(["open", "acknowledged"]),
        )
    )
    resolved_today = await eva_db.execute(
        select(func.count(EvaMonitoringIssue.id)).where(
            EvaMonitoringIssue.status == "resolved",
            EvaMonitoringIssue.resolved_at >= today_start,
        )
    )

    return MonitoringOverviewResponse(
        open_critical=critical.scalar() or 0,
        open_high=high.scalar() or 0,
        total_open=total_open.scalar() or 0,
        resolved_today=resolved_today.scalar() or 0,
    )


@router.get("/monitoring/issues", response_model=list[MonitoringIssueResponse])
async def list_issues(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    q = select(EvaMonitoringIssue).order_by(EvaMonitoringIssue.last_seen_at.desc())
    if status:
        q = q.where(EvaMonitoringIssue.status == status)
    if severity:
        q = q.where(EvaMonitoringIssue.severity == severity)
    result = await eva_db.execute(q)
    return result.scalars().all()


@router.get("/monitoring/checks", response_model=list[MonitoringCheckResponse])
async def list_checks(
    service: str | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    q = select(EvaMonitoringCheck).order_by(EvaMonitoringCheck.checked_at.desc())
    if service:
        q = q.where(EvaMonitoringCheck.service == service)
    result = await eva_db.execute(q)
    return result.scalars().all()


@router.post("/monitoring/issues/{issue_id}/acknowledge", response_model=MonitoringIssueResponse)
async def acknowledge_issue(
    issue_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(
        select(EvaMonitoringIssue).where(EvaMonitoringIssue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status == "resolved":
        raise HTTPException(status_code=400, detail="Issue is already resolved")
    issue.status = "acknowledged"
    issue.acknowledged_at = datetime.now(timezone.utc)
    eva_db.add(issue)
    return issue


@router.post("/monitoring/issues/{issue_id}/resolve", response_model=MonitoringIssueResponse)
async def resolve_issue(
    issue_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(
        select(EvaMonitoringIssue).where(EvaMonitoringIssue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    issue.status = "resolved"
    issue.resolved_at = datetime.now(timezone.utc)
    eva_db.add(issue)
    return issue
