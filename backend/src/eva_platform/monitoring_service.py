"""Monitoring service runner and issue automation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import engine, eva_async_session, eva_engine
from src.eva_platform.models import EvaMonitoringCheck, EvaMonitoringIssue

logger = logging.getLogger(__name__)

FAILURE_STATES = {"down", "degraded"}


@dataclass(frozen=True, slots=True)
class CheckSpec:
    check_key: str
    service: str
    target: str
    critical: bool
    category: str
    kind: str = "http"
    headers: dict[str, str] = field(default_factory=dict)
    success_statuses: tuple[int, ...] = ()
    api_key: str = ""


@dataclass(slots=True)
class CheckResult:
    check_key: str
    service: str
    target: str
    status: str
    critical: bool
    category: str
    checked_at: datetime
    http_status: int | None = None
    latency_ms: float | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_success_at: datetime | None = None
    stale: bool = False


def classify_http_status(status_code: int, success_statuses: tuple[int, ...] = ()) -> str:
    if success_statuses and status_code in success_statuses:
        return "up"
    if status_code < 400:
        return "up"
    if status_code < 500:
        return "degraded"
    return "down"


def compute_streaks(prev_failures: int, prev_successes: int, current_status: str) -> tuple[int, int]:
    if current_status == "up":
        return 0, prev_successes + 1
    return prev_failures + 1, 0


def classify_issue_severity(status: str, critical: bool) -> str:
    if status == "down":
        return "critical" if critical else "high"
    if status == "degraded":
        return "high" if critical else "medium"
    return "low"


def _build_check_specs() -> list[CheckSpec]:
    supabase_base = (settings.supabase_url or settings.monitoring_supabase_url).rstrip("/")
    erp_frontend_target = settings.monitoring_erp_frontend_url or settings.monitoring_frontend_url
    eva_app_frontend_target = (
        settings.monitoring_eva_app_frontend_url or settings.monitoring_frontend_url
    )
    facturapi_fmac_key = settings.monitoring_facturapi_fmac_api_key or settings.facturapi_api_key
    facturapi_eva_erp_key = (
        settings.monitoring_facturapi_eva_erp_api_key or settings.facturapi_api_key
    )
    facturapi_eva_app_key = (
        settings.monitoring_facturapi_eva_app_api_key or settings.facturapi_api_key
    )

    specs: list[CheckSpec] = [
        CheckSpec(
            check_key="erp-db",
            service="ERP Database",
            target="erp-db",
            critical=True,
            category="database",
            kind="erp_db",
        ),
        CheckSpec(
            check_key="eva-db",
            service="EVA Database",
            target="eva-db",
            critical=True,
            category="database",
            kind="eva_db",
        ),
        CheckSpec(
            check_key="erp-api",
            service="ERP API",
            target=settings.monitoring_erp_api_health_url,
            critical=True,
            category="api",
        ),
        CheckSpec(
            check_key="erp-frontend",
            service="ERP Frontend",
            target=erp_frontend_target,
            critical=True,
            category="frontend",
        ),
        CheckSpec(
            check_key="eva-app-frontend",
            service="EVA App Frontend",
            target=eva_app_frontend_target,
            critical=True,
            category="frontend",
        ),
        CheckSpec(
            check_key="fmac-erp-frontend",
            service="FMAccesorios ERP Frontend",
            target=settings.monitoring_fmac_erp_frontend_url,
            critical=True,
            category="frontend",
        ),
        CheckSpec(
            check_key="fmac-erp-backend",
            service="FMAccesorios ERP Backend",
            target=settings.monitoring_fmac_erp_backend_url,
            critical=True,
            category="api",
            success_statuses=(200, 401, 403),
        ),
        CheckSpec(
            check_key="fmac-erp-db",
            service="FMAccesorios ERP Database",
            target=settings.monitoring_fmac_erp_db_url,
            critical=True,
            category="database",
            kind="external_db",
        ),
        CheckSpec(
            check_key="eva-api",
            service="EVA API",
            target=settings.monitoring_eva_api_health_url,
            critical=True,
            category="api",
        ),
        CheckSpec(
            check_key="openai-api",
            service="OpenAI API",
            target="https://api.openai.com/v1/models",
            critical=False,
            category="ai",
            kind="openai",
        ),
        CheckSpec(
            check_key="facturapi-fmac-erp",
            service="FacturAPI (FMAccesorios ERP)",
            target=settings.monitoring_facturapi_fmac_url,
            critical=False,
            category="billing",
            kind="facturapi",
            api_key=facturapi_fmac_key,
        ),
        CheckSpec(
            check_key="facturapi-eva-erp",
            service="FacturAPI (EVA ERP)",
            target=settings.monitoring_facturapi_eva_erp_url,
            critical=False,
            category="billing",
            kind="facturapi",
            api_key=facturapi_eva_erp_key,
        ),
        CheckSpec(
            check_key="facturapi-eva-app",
            service="FacturAPI (EVA app)",
            target=settings.monitoring_facturapi_eva_app_url,
            critical=False,
            category="billing",
            kind="facturapi",
            api_key=facturapi_eva_app_key,
        ),
    ]

    if settings.monitoring_whatsapp_health_url:
        specs.append(
            CheckSpec(
                check_key="eva-whatsapp",
                service="EVA WhatsApp",
                target=settings.monitoring_whatsapp_health_url,
                critical=False,
                category="messaging",
            )
        )

    if supabase_base:
        specs.append(
            CheckSpec(
                check_key="supabase-auth",
                service="Supabase Auth",
                target=f"{supabase_base}/auth/v1/health",
                critical=True,
                category="auth",
            )
        )
        specs.append(
            CheckSpec(
                check_key="supabase-admin",
                service="Supabase Admin",
                target=f"{supabase_base}/auth/v1/admin/users?page=1&per_page=1",
                critical=True,
                category="auth",
                kind="supabase_admin",
            )
        )

    return specs


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _run_http_check(client: httpx.AsyncClient, spec: CheckSpec) -> CheckResult:
    if not spec.target:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="Monitoring target is not configured",
        )

    try:
        start = asyncio.get_running_loop().time()
        response = await client.get(spec.target, headers=spec.headers)
        latency_ms = (asyncio.get_running_loop().time() - start) * 1000
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status=classify_http_status(response.status_code, spec.success_statuses),
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            http_status=response.status_code,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="down",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message=str(exc)[:300],
        )


async def _run_openai_check(client: httpx.AsyncClient, spec: CheckSpec) -> CheckResult:
    if not settings.openai_api_key:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="OPENAI_API_KEY not configured",
        )
    auth_headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    custom = CheckSpec(
        check_key=spec.check_key,
        service=spec.service,
        target=spec.target,
        critical=spec.critical,
        category=spec.category,
        kind=spec.kind,
        headers=auth_headers,
    )
    return await _run_http_check(client, custom)


async def _run_facturapi_check(client: httpx.AsyncClient, spec: CheckSpec) -> CheckResult:
    facturapi_api_key = spec.api_key or settings.facturapi_api_key
    if not facturapi_api_key:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="FacturAPI API key not configured",
        )
    headers = {"Authorization": f"Bearer {facturapi_api_key}"}
    custom = CheckSpec(
        check_key=spec.check_key,
        service=spec.service,
        target=spec.target,
        critical=spec.critical,
        category=spec.category,
        kind=spec.kind,
        headers=headers,
        api_key=facturapi_api_key,
    )
    return await _run_http_check(client, custom)


async def _run_supabase_admin_check(client: httpx.AsyncClient, spec: CheckSpec) -> CheckResult:
    if not settings.supabase_service_role_key:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="SUPABASE_SERVICE_ROLE_KEY not configured",
        )
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    custom = CheckSpec(
        check_key=spec.check_key,
        service=spec.service,
        target=spec.target,
        critical=spec.critical,
        category=spec.category,
        kind=spec.kind,
        headers=headers,
    )
    return await _run_http_check(client, custom)


async def _run_erp_db_check(spec: CheckSpec) -> CheckResult:
    try:
        start = asyncio.get_running_loop().time()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (asyncio.get_running_loop().time() - start) * 1000
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="up",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="down",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message=str(exc)[:300],
        )


async def _run_eva_db_check(spec: CheckSpec) -> CheckResult:
    if eva_engine is None:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="EVA_DATABASE_URL not configured",
        )
    try:
        start = asyncio.get_running_loop().time()
        async with eva_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (asyncio.get_running_loop().time() - start) * 1000
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="up",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="down",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message=str(exc)[:300],
        )


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


async def _run_external_db_check(spec: CheckSpec) -> CheckResult:
    if not spec.target:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="degraded",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message="External DB URL is not configured",
        )

    try:
        start = asyncio.get_running_loop().time()
        conn = await asyncpg.connect(
            _normalize_postgres_url(spec.target),
            timeout=max(float(settings.monitoring_check_timeout_seconds), 1.0),
        )
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        latency_ms = (asyncio.get_running_loop().time() - start) * 1000
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="up",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="down",
            critical=spec.critical,
            category=spec.category,
            checked_at=_now_utc(),
            error_message=str(exc)[:300],
        )


async def _run_single_check(client: httpx.AsyncClient, spec: CheckSpec) -> CheckResult:
    if spec.kind == "erp_db":
        return await _run_erp_db_check(spec)
    if spec.kind == "eva_db":
        return await _run_eva_db_check(spec)
    if spec.kind == "external_db":
        return await _run_external_db_check(spec)
    if spec.kind == "openai":
        return await _run_openai_check(client, spec)
    if spec.kind == "facturapi":
        return await _run_facturapi_check(client, spec)
    if spec.kind == "supabase_admin":
        return await _run_supabase_admin_check(client, spec)
    return await _run_http_check(client, spec)


async def run_live_checks(exclude_check_keys: set[str] | None = None) -> list[CheckResult]:
    specs = _build_check_specs()
    if exclude_check_keys:
        specs = [spec for spec in specs if spec.check_key not in exclude_check_keys]
    timeout = max(float(settings.monitoring_check_timeout_seconds), 1.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [_run_single_check(client, spec) for spec in specs]
        return list(await asyncio.gather(*tasks))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _latest_check_for_key(eva_db: AsyncSession, check_key: str) -> EvaMonitoringCheck | None:
    row = await eva_db.execute(
        select(EvaMonitoringCheck)
        .where(EvaMonitoringCheck.check_key == check_key)
        .order_by(EvaMonitoringCheck.checked_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


def _issue_fingerprint(check_key: str) -> str:
    return f"monitoring:{check_key}"


def _issue_title(result: CheckResult) -> str:
    if result.status == "up":
        return f"{result.service} recovered"
    return f"{result.service} is {result.status}"


def _issue_summary(result: CheckResult) -> str:
    if result.error_message:
        return result.error_message
    if result.http_status is not None:
        return f"HTTP {result.http_status}"
    return f"Status {result.status}"


async def _send_slack_alert(event: str, issue: EvaMonitoringIssue, result: CheckResult) -> None:
    webhook = settings.monitoring_slack_webhook_url.strip()
    if not webhook:
        return

    if event == "opened":
        prefix = "Issue opened"
    elif event == "reopened":
        prefix = "Issue reopened"
    else:
        prefix = "Issue resolved"

    text_message = (
        f"*{prefix}*\n"
        f"Service: `{result.service}`\n"
        f"Severity: `{issue.severity}`\n"
        f"Status: `{result.status}`\n"
        f"Title: {issue.title}\n"
        f"Occurrences: {issue.occurrences}"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook, json={"text": text_message})
    except Exception:
        logger.warning("Failed to send Slack monitoring alert", exc_info=True)


async def _apply_issue_rules(eva_db: AsyncSession, result: CheckResult) -> None:
    fingerprint = _issue_fingerprint(result.check_key)
    issue_q = await eva_db.execute(
        select(EvaMonitoringIssue).where(EvaMonitoringIssue.fingerprint == fingerprint)
    )
    issue = issue_q.scalar_one_or_none()

    failure_threshold = (
        settings.monitoring_failure_threshold_critical
        if result.critical
        else settings.monitoring_failure_threshold_default
    )
    should_open = (
        result.status in FAILURE_STATES and result.consecutive_failures >= max(failure_threshold, 1)
    )
    should_resolve = (
        result.status == "up" and result.consecutive_successes >= max(settings.monitoring_recovery_threshold, 1)
    )

    if should_open:
        opened_event: str | None = None
        if issue is None:
            issue = EvaMonitoringIssue(
                fingerprint=fingerprint,
                source="monitoring_runner",
                category=result.category,
                severity=classify_issue_severity(result.status, result.critical),
                status="open",
                title=_issue_title(result),
                summary=_issue_summary(result),
                occurrences=1,
                sample_payload={
                    "target": result.target,
                    "http_status": result.http_status,
                    "error": result.error_message,
                },
                context_payload={
                    "check_key": result.check_key,
                    "critical": result.critical,
                    "consecutive_failures": result.consecutive_failures,
                    "last_success_at": result.last_success_at.isoformat() if result.last_success_at else None,
                },
                first_seen_at=result.checked_at,
                last_seen_at=result.checked_at,
                acknowledged_at=None,
                resolved_at=None,
            )
            eva_db.add(issue)
            opened_event = "opened"
        else:
            was_resolved = issue.status == "resolved"
            if was_resolved:
                issue.status = "open"
                issue.resolved_at = None
                issue.acknowledged_at = None
                opened_event = "reopened"
            issue.severity = classify_issue_severity(result.status, result.critical)
            issue.category = result.category
            issue.title = _issue_title(result)
            issue.summary = _issue_summary(result)
            issue.last_seen_at = result.checked_at
            issue.occurrences = (issue.occurrences or 0) + 1
            issue.context_payload = {
                "check_key": result.check_key,
                "critical": result.critical,
                "consecutive_failures": result.consecutive_failures,
                "last_success_at": result.last_success_at.isoformat() if result.last_success_at else None,
            }
            issue.sample_payload = {
                "target": result.target,
                "http_status": result.http_status,
                "error": result.error_message,
            }
            eva_db.add(issue)

        if opened_event is not None:
            await _send_slack_alert(opened_event, issue, result)
        return

    if should_resolve and issue and issue.status in {"open", "acknowledged"}:
        issue.status = "resolved"
        issue.resolved_at = result.checked_at
        issue.last_seen_at = result.checked_at
        issue.summary = _issue_summary(result)
        eva_db.add(issue)
        await _send_slack_alert("resolved", issue, result)


async def persist_monitoring_results(
    eva_db: AsyncSession, results: list[CheckResult]
) -> list[CheckResult]:
    for result in results:
        previous = await _latest_check_for_key(eva_db, result.check_key)
        previous_details = previous.details or {} if previous else {}
        prev_fail = int(previous_details.get("consecutive_failures", 0) or 0)
        prev_success = int(previous_details.get("consecutive_successes", 0) or 0)

        fail_streak, success_streak = compute_streaks(prev_fail, prev_success, result.status)
        result.consecutive_failures = fail_streak
        result.consecutive_successes = success_streak

        if result.status == "up":
            result.last_success_at = result.checked_at
        else:
            result.last_success_at = _parse_dt(previous_details.get("last_success_at"))

        details = {
            "critical": result.critical,
            "category": result.category,
            "consecutive_failures": result.consecutive_failures,
            "consecutive_successes": result.consecutive_successes,
            "last_success_at": result.last_success_at.isoformat() if result.last_success_at else None,
        }
        if result.details:
            details.update(result.details)

        eva_db.add(
            EvaMonitoringCheck(
                check_key=result.check_key,
                service=result.service,
                target=result.target,
                status=result.status,
                http_status=result.http_status,
                latency_ms=result.latency_ms,
                error_message=result.error_message,
                details=details,
                checked_at=result.checked_at,
            )
        )
        await _apply_issue_rules(eva_db, result)

    return results


async def run_monitoring_cycle(eva_db: AsyncSession | None = None) -> list[CheckResult]:
    results = await run_live_checks()
    if eva_db is not None:
        await persist_monitoring_results(eva_db, results)
    return results


def check_result_to_service_item(result: CheckResult) -> dict[str, Any]:
    return {
        "check_key": result.check_key,
        "name": result.service,
        "url": result.target,
        "status": result.status,
        "latency_ms": int(result.latency_ms) if result.latency_ms is not None else None,
        "http_status": result.http_status,
        "error": result.error_message,
        "checked_at": result.checked_at,
        "critical": result.critical,
        "consecutive_failures": result.consecutive_failures,
        "consecutive_successes": result.consecutive_successes,
        "last_success_at": result.last_success_at,
        "stale": result.stale,
    }


async def latest_service_items_from_db(eva_db: AsyncSession) -> list[dict[str, Any]]:
    specs = _build_check_specs()
    check_keys = [s.check_key for s in specs]
    if not check_keys:
        return []

    rows = (
        await eva_db.execute(
            select(EvaMonitoringCheck)
            .where(EvaMonitoringCheck.check_key.in_(check_keys))
            .order_by(EvaMonitoringCheck.checked_at.desc())
            .limit(max(len(check_keys) * 20, 100))
        )
    ).scalars().all()

    latest_by_key: dict[str, EvaMonitoringCheck] = {}
    for row in rows:
        if row.check_key not in latest_by_key:
            latest_by_key[row.check_key] = row
        if len(latest_by_key) == len(check_keys):
            break

    stale_after = max(settings.monitoring_stale_after_seconds, 30)
    now = _now_utc()
    items: list[dict[str, Any]] = []

    for spec in specs:
        row = latest_by_key.get(spec.check_key)
        if row is None:
            items.append(
                {
                    "check_key": spec.check_key,
                    "name": spec.service,
                    "url": spec.target,
                    "status": "down",
                    "latency_ms": None,
                    "http_status": None,
                    "error": "No monitoring data yet",
                    "checked_at": None,
                    "critical": spec.critical,
                    "consecutive_failures": 0,
                    "consecutive_successes": 0,
                    "last_success_at": None,
                    "stale": True,
                }
            )
            continue

        details = row.details or {}
        checked_at = row.checked_at
        stale = checked_at is None or (now - checked_at).total_seconds() > stale_after
        status = row.status
        error_message = row.error_message
        if stale and status == "up":
            status = "degraded"
            error_message = "Monitoring data is stale"

        items.append(
            {
                "check_key": row.check_key,
                "name": row.service,
                "url": row.target,
                "status": status,
                "latency_ms": int(row.latency_ms) if row.latency_ms is not None else None,
                "http_status": row.http_status,
                "error": error_message,
                "checked_at": checked_at,
                "critical": bool(details.get("critical", spec.critical)),
                "consecutive_failures": int(details.get("consecutive_failures", 0) or 0),
                "consecutive_successes": int(details.get("consecutive_successes", 0) or 0),
                "last_success_at": _parse_dt(details.get("last_success_at")),
                "stale": stale,
            }
        )

    return items


def should_refresh_service_snapshot(items: list[dict[str, Any]]) -> bool:
    if not items:
        return True
    now = _now_utc()
    refresh_after = max(settings.monitoring_interval_seconds * 2, 30)
    latest_checked_at: datetime | None = None
    for item in items:
        checked_at = item.get("checked_at")
        if isinstance(checked_at, datetime):
            if latest_checked_at is None or checked_at > latest_checked_at:
                latest_checked_at = checked_at
        if item.get("critical") and item.get("stale"):
            return True
    if latest_checked_at is None:
        return True
    return (now - latest_checked_at).total_seconds() > refresh_after


async def monitoring_runner_loop(stop_event: asyncio.Event) -> None:
    """Background monitoring loop with periodic checks."""
    if not settings.monitoring_enabled:
        logger.info("Monitoring runner disabled")
        return

    interval = max(settings.monitoring_interval_seconds, 10)
    logger.info("Monitoring runner started (interval=%ss)", interval)

    while not stop_event.is_set():
        try:
            if eva_async_session is None:
                await run_monitoring_cycle(None)
            else:
                async with eva_async_session() as eva_db:
                    await run_monitoring_cycle(eva_db)
                    await eva_db.commit()
        except Exception:
            logger.exception("Monitoring cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue

    logger.info("Monitoring runner stopped")
