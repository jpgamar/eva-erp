"""Monitoring dashboard: read from Eva's monitoring tables."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_eva_db
from src.eva_platform.models import EvaMonitoringCheck, EvaMonitoringIssue
from src.eva_platform.schemas import (
    MonitoringCheckResponse,
    MonitoringIssueResponse,
    MonitoringOverviewResponse,
)

router = APIRouter()


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
