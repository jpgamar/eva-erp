"""Empresa item reminder dispatcher tests.

Pure unit tests with monkeypatched session + SendGrid client. Asserts:
- 24h / 1h windows return the right rows.
- Atomic claim sets the sent column BEFORE the SendGrid call.
- SendGrid failure compensates by reverting the claim.
- Done items + notes are skipped.
- Past events are stamped on create / edit (router behavior).
- Internal items (`empresa_id IS NULL`) participate.
- Recipient resolution honors the env override.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.empresas import reminders


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Each test starts with predictable env: known recipient, sendgrid configured."""
    monkeypatch.setattr(reminders.settings, "sendgrid_api_key", "SG.fake-key", raising=False)
    monkeypatch.setattr(reminders.settings, "empresa_item_reminder_email", "gus@goeva.ai", raising=False)


def _make_claim(start_at: _dt.datetime, *, empresa_name: str | None = "Acme") -> reminders._ClaimedItem:
    return reminders._ClaimedItem(
        id=str(uuid.uuid4()),
        empresa_id=str(uuid.uuid4()) if empresa_name is not None else None,
        title="Llamar Juan",
        description="Confirmar agenda",
        start_at=start_at,
        empresa_name=empresa_name,
    )


@pytest.mark.parametrize("kind", ["24h", "1h"])
def test_send_email_success_returns_true(monkeypatch, kind):
    """A 200 from SendGrid means success — caller keeps the claim."""
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))

    captured = {}

    async def _fake_post(self, url, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return SimpleNamespace(status_code=202, text="ok")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        ok = asyncio.run(reminders._send_item_reminder_email(item, kind))
    assert ok is True
    assert captured["url"].endswith("/v3/mail/send")
    # Recipient + subject sanity
    payload = captured["json"]
    assert payload["personalizations"][0]["to"][0]["email"] == "gus@goeva.ai"
    expected_delta = "24 horas" if kind == "24h" else "1 hora"
    assert expected_delta in payload["personalizations"][0]["subject"]
    assert "Llamar Juan" in payload["personalizations"][0]["subject"]


def test_send_email_internal_item_uses_tarea_interna_label(monkeypatch):
    """Items with empresa_id NULL render 'Tarea interna' in the body."""
    item = _make_claim(
        _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24), empresa_name=None
    )

    captured = {}

    async def _fake_post(self, url, headers=None, json=None):
        captured["json"] = json
        return SimpleNamespace(status_code=202, text="ok")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        ok = asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert ok is True
    text_body = captured["json"]["content"][0]["value"]
    assert "Tarea interna" in text_body


def test_send_email_4xx_returns_false(monkeypatch):
    """SendGrid auth failure (4xx) is non-retryable inside the call;
    caller will revert the claim."""
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))

    async def _fake_post(self, url, headers=None, json=None):
        return SimpleNamespace(status_code=401, text="bad key")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        ok = asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert ok is False


def test_send_email_5xx_retries_once(monkeypatch):
    """A single 5xx triggers a retry; second 5xx returns False."""
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))
    calls = {"n": 0}

    async def _fake_post(self, url, headers=None, json=None):
        calls["n"] += 1
        return SimpleNamespace(status_code=503, text="upstream")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        with patch("asyncio.sleep", new=AsyncMock()):
            ok = asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert ok is False
    assert calls["n"] == 2


def test_send_email_5xx_then_success(monkeypatch):
    """5xx then 202 → caller sees success after one retry."""
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))
    statuses = iter([503, 202])

    async def _fake_post(self, url, headers=None, json=None):
        return SimpleNamespace(status_code=next(statuses), text="...")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        with patch("asyncio.sleep", new=AsyncMock()):
            ok = asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert ok is True


def test_send_email_no_api_key_returns_false(monkeypatch):
    monkeypatch.setattr(reminders.settings, "sendgrid_api_key", "", raising=False)
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))
    ok = asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert ok is False


def test_send_email_recipient_env_override(monkeypatch):
    monkeypatch.setattr(reminders.settings, "empresa_item_reminder_email", "another@example.com", raising=False)
    item = _make_claim(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24))
    captured = {}

    async def _fake_post(self, url, headers=None, json=None):
        captured["json"] = json
        return SimpleNamespace(status_code=202, text="ok")

    with patch("httpx.AsyncClient.post", new=_fake_post):
        asyncio.run(reminders._send_item_reminder_email(item, "24h"))
    assert captured["json"]["personalizations"][0]["to"][0]["email"] == "another@example.com"


# ── Dispatcher orchestration: claim + send + revert-on-failure ──────


class _FakeClaimSession:
    """Stand-in for AsyncSession used by `_dispatch_kind_once`.

    Records the SQL statements it sees so tests can assert atomic-claim
    behavior without a real DB.
    """

    def __init__(self, claim_returns: list[Any]) -> None:
        self.claim_returns = claim_returns
        self.executed: list[Any] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        # First call = claim UPDATE...RETURNING. Subsequent = empresa name lookup.
        if "RETURNING" in str(sql).upper():
            rows = self.claim_returns
            return SimpleNamespace(all=lambda: rows)
        # Empresa name lookup — return empty.
        return SimpleNamespace(all=lambda: [])

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


def test_dispatch_kind_once_send_success_keeps_claim(monkeypatch):
    """When SendGrid succeeds, no compensating UPDATE runs."""
    now = _dt.datetime.now(_dt.timezone.utc)
    fake_row = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=None,
        title="Visita",
        description=None,
        start_at=now + _dt.timedelta(hours=24),
    )
    sessions: list[_FakeClaimSession] = []

    def _session_factory():
        s = _FakeClaimSession([fake_row])
        sessions.append(s)
        return s

    monkeypatch.setattr(reminders, "async_session", _session_factory)

    async def _fake_send(item, kind):
        return True

    monkeypatch.setattr(reminders, "_send_item_reminder_email", _fake_send)
    asyncio.run(reminders._dispatch_kind_once("24h"))
    # Only the claim session should have been used; no revert session.
    assert len(sessions) == 1
    assert sessions[0].committed


def test_dispatch_kind_once_send_failure_reverts_claim(monkeypatch):
    """When SendGrid fails, dispatcher runs compensating UPDATE on a
    fresh session to release the claim."""
    now = _dt.datetime.now(_dt.timezone.utc)
    fake_row = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=None,
        title="Visita",
        description=None,
        start_at=now + _dt.timedelta(hours=24),
    )
    sessions: list[_FakeClaimSession] = []

    def _session_factory():
        s = _FakeClaimSession([fake_row])
        sessions.append(s)
        return s

    monkeypatch.setattr(reminders, "async_session", _session_factory)

    async def _fake_send(item, kind):
        return False

    monkeypatch.setattr(reminders, "_send_item_reminder_email", _fake_send)
    asyncio.run(reminders._dispatch_kind_once("24h"))
    # Two sessions: one for claim, one for revert.
    assert len(sessions) == 2
    revert_sql = sessions[1].executed[-1][0]
    assert "reminder_24h_sent_at = NULL" in revert_sql


def test_dispatch_kind_once_no_rows_no_send(monkeypatch):
    """Empty claim result → never call SendGrid."""
    sessions: list[_FakeClaimSession] = []

    def _session_factory():
        s = _FakeClaimSession([])
        sessions.append(s)
        return s

    monkeypatch.setattr(reminders, "async_session", _session_factory)

    sent = []

    async def _fake_send(item, kind):
        sent.append((item.id, kind))
        return True

    monkeypatch.setattr(reminders, "_send_item_reminder_email", _fake_send)
    asyncio.run(reminders._dispatch_kind_once("1h"))
    assert sent == []


def test_atomic_claim_sql_uses_for_update_skip_locked(monkeypatch):
    """The claim SQL MUST contain FOR UPDATE SKIP LOCKED + RETURNING so
    concurrent loops never double-send."""
    sessions: list[_FakeClaimSession] = []

    def _session_factory():
        s = _FakeClaimSession([])
        sessions.append(s)
        return s

    monkeypatch.setattr(reminders, "async_session", _session_factory)
    asyncio.run(reminders._dispatch_kind_once("24h"))

    claim_sql = sessions[0].executed[0][0]
    assert "FOR UPDATE SKIP LOCKED" in claim_sql
    assert "RETURNING" in claim_sql
    # Window correctness: 24h ±5min.
    assert "23 hours 55 minutes" in claim_sql
    assert "24 hours 5 minutes" in claim_sql
    # Filters
    assert "kind <> 'note'" in claim_sql
    assert "done = false" in claim_sql.lower()


# ── Past-event sentinel on create/edit ──────────────────────────────


def test_stamp_past_event_reminders_marks_both_columns():
    """Helper sets both columns to NOW for past events; leaves them
    alone for future events."""
    from src.empresas.router import _stamp_past_event_reminders
    from src.empresas.models import EmpresaItem

    past = EmpresaItem(
        id=uuid.uuid4(),
        empresa_id=None,
        title="Past",
        kind="event",
        start_at=_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1),
    )
    _stamp_past_event_reminders(past)
    assert past.reminder_24h_sent_at is not None
    assert past.reminder_1h_sent_at is not None

    future = EmpresaItem(
        id=uuid.uuid4(),
        empresa_id=None,
        title="Future",
        kind="event",
        start_at=_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2),
    )
    _stamp_past_event_reminders(future)
    assert future.reminder_24h_sent_at is None
    assert future.reminder_1h_sent_at is None
