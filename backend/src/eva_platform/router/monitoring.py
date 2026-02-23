"""Monitoring dashboard endpoints."""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_optional_eva_db
from src.eva_platform.models import EvaMonitoringCheck, EvaMonitoringIssue
from src.eva_platform.monitoring_service import (
    check_result_to_service_item,
    latest_service_items_from_db,
    run_monitoring_cycle,
    should_refresh_service_snapshot,
)
from src.eva_platform.schemas import (
    MonitoringCheckResponse,
    MonitoringIssueResponse,
    MonitoringOverviewResponse,
    ServiceStatusItem,
    ServiceStatusResponse,
)

router = APIRouter()


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _check_to_response(check: EvaMonitoringCheck) -> MonitoringCheckResponse:
    details = check.details or {}
    return MonitoringCheckResponse(
        id=check.id,
        check_key=check.check_key,
        service=check.service,
        target=check.target,
        status=check.status,
        http_status=check.http_status,
        latency_ms=check.latency_ms,
        error_message=check.error_message,
        details=details,
        consecutive_failures=int(details.get("consecutive_failures", 0) or 0),
        consecutive_successes=int(details.get("consecutive_successes", 0) or 0),
        last_success_at=_parse_dt(details.get("last_success_at")),
        critical=bool(details.get("critical", False)),
        checked_at=check.checked_at,
    )


@router.get("/monitoring/services", response_model=ServiceStatusResponse)
async def service_status(
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    """Service snapshot with auto-refresh when stale."""
    service_items: list[dict[str, Any]]

    if eva_db is None:
        results = await run_monitoring_cycle(None)
        service_items = [check_result_to_service_item(item) for item in results]
    else:
        service_items = await latest_service_items_from_db(eva_db)
        if should_refresh_service_snapshot(service_items):
            results = await run_monitoring_cycle(eva_db)
            service_items = [check_result_to_service_item(item) for item in results]

    checked_values = [
        item.get("checked_at")
        for item in service_items
        if isinstance(item.get("checked_at"), datetime)
    ]
    checked_at = max(checked_values) if checked_values else datetime.now(timezone.utc)
    return ServiceStatusResponse(
        services=[ServiceStatusItem(**item) for item in service_items],
        checked_at=checked_at,
    )


@router.get("/monitoring/overview", response_model=MonitoringOverviewResponse)
async def monitoring_overview(
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    if eva_db is None:
        return MonitoringOverviewResponse(
            open_critical=0,
            open_high=0,
            total_open=0,
            resolved_today=0,
        )

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
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    if eva_db is None:
        return []

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
    limit: int = Query(100, ge=1, le=500),
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    if eva_db is None:
        return []

    q = select(EvaMonitoringCheck)
    if service:
        q = q.where(EvaMonitoringCheck.service == service)
    q = q.order_by(EvaMonitoringCheck.checked_at.desc()).limit(limit)
    result = await eva_db.execute(q)
    return [_check_to_response(check) for check in result.scalars().all()]


@router.post("/monitoring/issues/{issue_id}/acknowledge", response_model=MonitoringIssueResponse)
async def acknowledge_issue(
    issue_id: uuid.UUID,
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    if eva_db is None:
        raise HTTPException(status_code=503, detail="Eva monitoring database is not configured")

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
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
    user: User = Depends(get_current_user),
):
    if eva_db is None:
        raise HTTPException(status_code=503, detail="Eva monitoring database is not configured")

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
