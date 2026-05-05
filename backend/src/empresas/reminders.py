"""Empresa item reminder dispatcher.

Sends one email at T-24h and one at T-1h for any `empresa_items` row with
a `start_at`. Concurrency-safe via atomic claim (UPDATE ... FOR UPDATE
SKIP LOCKED ... RETURNING) so two API instances never double-send.

Plan: docs/archive/plans/plan-empresas-ux-pass.md (Feature 3).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import async_session

logger = logging.getLogger(__name__)

ReminderKind = Literal["24h", "1h"]

# Window is ±5 min around the boundary so a 5-min loop tick can't miss
# anything. The dispatcher claims a row atomically before sending so
# concurrent loops never double-send.
_WINDOWS: dict[ReminderKind, tuple[str, str, str]] = {
    "24h": (
        "23 hours 55 minutes",
        "24 hours 5 minutes",
        "reminder_24h_sent_at",
    ),
    "1h": (
        "0 hours 55 minutes",
        "1 hour 5 minutes",
        "reminder_1h_sent_at",
    ),
}

# How long humans see ahead-of-time, e.g. "en 24 horas".
_HUMAN_DELTA: dict[ReminderKind, str] = {
    "24h": "24 horas",
    "1h": "1 hora",
}


@dataclass
class _ClaimedItem:
    id: str
    empresa_id: str | None
    title: str
    description: str | None
    start_at: datetime
    empresa_name: str | None


def _local_format(dt: datetime) -> str:
    """Render a UTC datetime in America/Mexico_City for the email body."""
    try:
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo("America/Mexico_City")).strftime("%d %b %Y, %H:%M")
    except Exception:  # pragma: no cover - zoneinfo always available on 3.12
        return dt.strftime("%Y-%m-%d %H:%M UTC")


async def _claim_due_items(session: AsyncSession, kind: ReminderKind) -> list[_ClaimedItem]:
    """Atomically claim rows whose `start_at` falls in the kind's window.

    The UPDATE ... FOR UPDATE SKIP LOCKED ... RETURNING idiom marks the
    sent-at column = NOW() in the same statement that selects the row,
    so concurrent loops cannot double-send. If the SendGrid call fails,
    the caller MUST run `_revert_claim()` to free the row for retry.
    """
    interval_low, interval_high, sent_col = _WINDOWS[kind]
    sql = text(
        f"""
        UPDATE empresa_items
           SET {sent_col} = NOW()
         WHERE id IN (
           SELECT ei.id FROM empresa_items ei
            WHERE ei.done = false
              AND ei.kind <> 'note'
              AND ei.start_at IS NOT NULL
              AND ei.{sent_col} IS NULL
              AND ei.start_at BETWEEN (NOW() + interval '{interval_low}')
                                  AND (NOW() + interval '{interval_high}')
            FOR UPDATE SKIP LOCKED
            LIMIT 50
         )
        RETURNING id, empresa_id, title, description, start_at;
        """
    )
    result = await session.execute(sql)
    rows = result.all()
    if not rows:
        return []

    claimed: list[_ClaimedItem] = []
    # Resolve empresa names in a single follow-up query.
    empresa_ids = [r.empresa_id for r in rows if r.empresa_id is not None]
    name_map: dict[str, str] = {}
    if empresa_ids:
        name_rows = await session.execute(
            text("SELECT id, name FROM empresas WHERE id = ANY(:ids)"),
            {"ids": empresa_ids},
        )
        name_map = {str(r.id): r.name for r in name_rows.all()}

    for r in rows:
        claimed.append(
            _ClaimedItem(
                id=str(r.id),
                empresa_id=str(r.empresa_id) if r.empresa_id else None,
                title=r.title,
                description=r.description,
                start_at=r.start_at,
                empresa_name=name_map.get(str(r.empresa_id)) if r.empresa_id else None,
            )
        )
    return claimed


async def _revert_claim(session: AsyncSession, kind: ReminderKind, item_id: str) -> None:
    """Compensating UPDATE: release the claim so the next tick retries.

    Called when SendGrid persistently fails for a single row. The 10-min
    window means we have a couple of retries before the boundary moves
    out of range.
    """
    _, _, sent_col = _WINDOWS[kind]
    await session.execute(
        text(f"UPDATE empresa_items SET {sent_col} = NULL WHERE id = :id"),
        {"id": item_id},
    )


async def _send_item_reminder_email(item: _ClaimedItem, kind: ReminderKind) -> bool:
    """Send the SendGrid email. Returns True on success, False on failure.

    Failure modes (matches plan):
      - 4xx (auth/permission): log error, return False (caller reverts claim).
      - 429/5xx: retry once with 30s backoff inside this call. If still
        failing, return False (caller reverts claim).
    """
    api_key = (settings.sendgrid_api_key or "").strip()
    if not api_key:
        logger.error("empresa_item_reminders.sendgrid_unconfigured item=%s", item.id)
        return False

    recipient = settings.empresa_item_reminder_email.strip().lower()
    if not recipient:
        logger.error("empresa_item_reminders.recipient_empty item=%s", item.id)
        return False

    sender_email = (settings.sendgrid_from_email or "no-reply@goeva.ai").strip()
    sender_name = (settings.sendgrid_from_name or "EvaAI").strip()
    reply_to = (settings.sendgrid_reply_to or "hi@goeva.ai").strip()
    delta_label = _HUMAN_DELTA[kind]
    when_label = _local_format(item.start_at)
    empresa_label = item.empresa_name or "Tarea interna"
    deeplink = f"https://erp.goeva.ai/empresas?view=tasks#item-{item.id}"
    description = item.description or ""

    subject = f"Recordatorio: {item.title} (en {delta_label})"
    body_text = (
        f"Recordatorio del CRM: {item.title}\n"
        f"Empresa: {empresa_label}\n"
        f"Cuando: {when_label} (en {delta_label})\n"
        f"\n{description}\n\n"
        f"Abrir: {deeplink}"
    )
    body_html = (
        '<div style="margin:0;padding:24px;background:#f8fafc;'
        'font-family:Arial,sans-serif;color:#0f172a;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;'
        'border:1px solid #e2e8f0;border-radius:10px;padding:24px;">'
        '<p style="margin:0 0 8px 0;font-size:13px;color:#64748b;text-transform:uppercase;'
        f'letter-spacing:0.06em;">Recordatorio · en {delta_label}</p>'
        f'<h1 style="margin:0 0 12px 0;font-size:20px;line-height:1.3;color:#0f172a;">{item.title}</h1>'
        f'<p style="margin:0 0 6px 0;font-size:14px;color:#0f172a;">'
        f'<strong>Empresa:</strong> {empresa_label}</p>'
        f'<p style="margin:0 0 16px 0;font-size:14px;color:#0f172a;">'
        f'<strong>Cuando:</strong> {when_label}</p>'
        + (
            f'<p style="margin:0 0 16px 0;font-size:14px;color:#475569;line-height:1.5;">{description}</p>'
            if description
            else ""
        )
        + f'<a href="{deeplink}" style="display:inline-block;background:#2563eb;color:#ffffff;'
        'text-decoration:none;font-weight:600;font-size:14px;padding:10px 16px;border-radius:8px;">'
        "Abrir en CRM</a>"
        "</div></div>"
    )

    payload = {
        "personalizations": [{"to": [{"email": recipient}], "subject": subject}],
        "from": {"email": sender_email, "name": sender_name},
        "reply_to": {"email": reply_to},
        "mail_settings": {"bypass_list_management": {"enable": True}},
        "tracking_settings": {
            "click_tracking": {"enable": False, "enable_text": False},
            "open_tracking": {"enable": False},
            "subscription_tracking": {"enable": False},
        },
        "content": [
            {"type": "text/plain", "value": body_text},
            {"type": "text/html", "value": body_html},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in (1, 2):
            try:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send", headers=headers, json=payload
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "empresa_item_reminders.transport_error item=%s attempt=%s err=%s",
                    item.id,
                    attempt,
                    exc,
                )
                if attempt == 1:
                    await asyncio.sleep(30)
                    continue
                return False

            if 200 <= resp.status_code < 300:
                return True
            if 400 <= resp.status_code < 500:
                logger.error(
                    "empresa_item_reminders.sendgrid_4xx item=%s status=%s body=%s",
                    item.id,
                    resp.status_code,
                    resp.text[:200],
                )
                return False
            # 5xx / 429 — retry once
            if attempt == 1:
                logger.warning(
                    "empresa_item_reminders.sendgrid_retryable item=%s status=%s",
                    item.id,
                    resp.status_code,
                )
                await asyncio.sleep(30)
                continue
            logger.error(
                "empresa_item_reminders.sendgrid_persistent_failure item=%s status=%s",
                item.id,
                resp.status_code,
            )
            return False
    return False


async def _dispatch_kind_once(kind: ReminderKind) -> None:
    """One pass for the given window kind. Claims rows, sends emails,
    reverts claims that failed.

    Each claim+send is its own session to keep transactions short.
    """
    async with async_session() as session:
        try:
            claimed = await _claim_due_items(session, kind)
            await session.commit()
        except Exception:
            logger.exception("empresa_item_reminders.claim_failed kind=%s", kind)
            await session.rollback()
            return

    for item in claimed:
        ok = False
        try:
            ok = await _send_item_reminder_email(item, kind)
        except Exception:
            logger.exception("empresa_item_reminders.send_unexpected item=%s kind=%s", item.id, kind)

        if not ok:
            async with async_session() as session:
                try:
                    await _revert_claim(session, kind, item.id)
                    await session.commit()
                except Exception:
                    logger.exception(
                        "empresa_item_reminders.revert_failed item=%s kind=%s", item.id, kind
                    )
                    await session.rollback()


async def empresa_item_reminder_runner_loop(stop_event: asyncio.Event) -> None:
    """Async background loop. Runs inside the FastAPI lifespan next to
    `monitoring_runner_loop`. Sleeps the configured interval between
    ticks, processes both windows on each tick.

    Loop NEVER exits on its own — only on `stop_event.set()` from
    FastAPI shutdown. This matches the convention of the monitoring loop.
    """
    interval = max(int(settings.empresa_item_reminder_loop_interval_seconds or 300), 30)
    logger.info(
        "empresa_item_reminders.loop_started interval=%ss recipient=%s",
        interval,
        settings.empresa_item_reminder_email,
    )
    while not stop_event.is_set():
        try:
            await _dispatch_kind_once("24h")
            await _dispatch_kind_once("1h")
        except Exception:
            logger.exception("empresa_item_reminders.tick_failed (loop continues)")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
    logger.info("empresa_item_reminders.loop_stopped")
