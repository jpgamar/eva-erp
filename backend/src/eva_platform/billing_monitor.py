"""Report billing issues to Eva's monitoring dashboard.

Uses the same EvaMonitoringIssue table that health checks use,
so billing failures appear alongside infrastructure issues on
erp.goeva.ai/monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.common.database import eva_async_session
from src.eva_platform.models import EvaMonitoringIssue

logger = logging.getLogger(__name__)


async def report_billing_issue(
    *,
    category: str,
    severity: str,
    title: str,
    summary: str,
    empresa_id: str | None = None,
    empresa_name: str | None = None,
    stripe_invoice_id: str | None = None,
    error: str | None = None,
    context: dict | None = None,
) -> None:
    """Write a billing issue to Eva's monitoring dashboard.

    Categories:
        billing_cfdi_failure   — CFDI stamp failed after payment (critical)
        billing_email_failure  — Factura email failed to send (high)
        billing_webhook_error  — Stripe webhook handler crashed (high)
        billing_fiscal_incomplete — CFDI skipped due to missing fiscal data (medium)
    """
    if eva_async_session is None:
        logger.warning("billing_monitor: Eva DB not configured, skipping issue report: %s", title)
        return

    fingerprint = f"billing:{category}:{empresa_id or 'unknown'}:{stripe_invoice_id or 'none'}"
    now = datetime.now(timezone.utc)

    sample_payload = {
        "empresa_name": empresa_name,
        "stripe_invoice_id": stripe_invoice_id,
        "error": error,
    }
    context_payload = {
        "empresa_id": empresa_id,
        **(context or {}),
    }

    try:
        async with eva_async_session() as db:
            result = await db.execute(
                select(EvaMonitoringIssue).where(EvaMonitoringIssue.fingerprint == fingerprint)
            )
            issue = result.scalar_one_or_none()

            if issue is None:
                issue = EvaMonitoringIssue(
                    fingerprint=fingerprint,
                    source="erp_billing",
                    category=category,
                    severity=severity,
                    status="open",
                    title=title,
                    summary=summary,
                    occurrences=1,
                    sample_payload=sample_payload,
                    context_payload=context_payload,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(issue)
            else:
                # Reopen if resolved
                if issue.status == "resolved":
                    issue.status = "open"
                    issue.resolved_at = None
                    issue.acknowledged_at = None
                issue.last_seen_at = now
                issue.occurrences = (issue.occurrences or 0) + 1
                issue.sample_payload = sample_payload
                issue.context_payload = context_payload
                issue.summary = summary
                issue.severity = severity
                db.add(issue)

            await db.commit()
            logger.info("billing_monitor: reported %s issue for empresa %s", category, empresa_name or empresa_id)

    except Exception:
        logger.warning("billing_monitor: failed to report issue (Eva DB may be unavailable)", exc_info=True)
