"""Unit tests for the Empresa channel-health link logic.

Tests cover:
- The auto-match-by-name routine (``_attempt_auto_match``)
- The per-empresa health computation (``_compute_health_for_empresas``)
- Schema parsing for the new ``EmpresaHealth`` and related models

These are pure-unit tests using fake DB sessions, matching the
existing pattern in ``tests/test_facturas_router.py``. No real
Postgres connection is required.

Plan: docs/domains/integrations/instagram/plan-silent-channel-health.md
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from typing import Any

import pytest

from src.empresas.models import Empresa
from src.empresas.router import _attempt_auto_match, _compute_health_for_empresas
from src.empresas.schemas import (
    AccountChannelHealthResponse,
    ChannelHealthEntry,
    EmpresaHealth,
    EvaAccountForLink,
)


# Named tuples that mimic SQLAlchemy result rows. The production code
# accesses .id, .name, etc., so plain tuples don't work in these tests.
_AccountRow = namedtuple("_AccountRow", ["id", "name"])  # for accounts query
_ChannelRow = namedtuple("_ChannelRow", ["is_healthy", "account_id"])  # for channel rows


def _empty_health(status: str) -> dict:
    """Build the empty-health shape for assertions."""
    return {
        "status": status,
        "unhealthy_count": 0,
        "linked_account_name": None,
        "messenger": {"present": False, "healthy": False, "count": 0},
        "instagram": {"present": False, "healthy": False, "count": 0},
    }


def _health(
    status: str,
    *,
    unhealthy_count: int = 0,
    linked_account_name: str | None = None,
    msg_present: bool = False,
    msg_healthy: bool = False,
    msg_count: int = 0,
    ig_present: bool = False,
    ig_healthy: bool = False,
    ig_count: int = 0,
) -> dict:
    return {
        "status": status,
        "unhealthy_count": unhealthy_count,
        "linked_account_name": linked_account_name,
        "messenger": {"present": msg_present, "healthy": msg_healthy, "count": msg_count},
        "instagram": {"present": ig_present, "healthy": ig_healthy, "count": ig_count},
    }


# ──────────────────────────────────────────────────────────────────────
# Fakes
# ──────────────────────────────────────────────────────────────────────


class _FakeScalarsResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def all(self) -> list[Any]:
        return self._values


class _FakeRowResult:
    """Result of execute() that supports both .scalars().all() and .all()."""

    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> _FakeScalarsResult:
        return _FakeScalarsResult(self._values)

    def all(self) -> list[Any]:
        return self._values


class _FakeEvaDB:
    """Minimal fake of an AsyncSession that returns a queue of results."""

    def __init__(self, results: list[Any]) -> None:
        # ``results`` is a list of either:
        # - list-of-values to return from .scalars().all() or .all()
        # - an Exception to raise
        self._results = results
        self._idx = 0
        self.executed = []  # for assertions if needed

    async def execute(self, query: Any) -> _FakeRowResult:
        self.executed.append(query)
        if self._idx >= len(self._results):
            raise AssertionError(
                f"FakeEvaDB ran out of canned results after {self._idx} calls"
            )
        result = self._results[self._idx]
        self._idx += 1
        if isinstance(result, Exception):
            raise result
        return _FakeRowResult(result)


class _FakeLocalDB:
    """Local DB session — auto-match doesn't query through it, only flushes."""

    def __init__(self) -> None:
        self.flushed = False

    async def flush(self) -> None:
        self.flushed = True


# ──────────────────────────────────────────────────────────────────────
# _attempt_auto_match
# ──────────────────────────────────────────────────────────────────────


def _make_empresa(name: str, **kwargs: Any) -> Empresa:
    return Empresa(
        id=uuid.uuid4(),
        name=name,
        eva_account_id=kwargs.get("eva_account_id"),
        auto_match_attempted=kwargs.get("auto_match_attempted", False),
    )


def test_auto_match_skips_already_attempted():
    empresa = _make_empresa("Lucky Telecom", auto_match_attempted=True)
    eva_db = _FakeEvaDB([])  # should never be called
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    assert empresa.auto_match_attempted is True
    assert empresa.eva_account_id is None
    assert eva_db._idx == 0  # never queried


def test_auto_match_skips_already_linked():
    existing_id = uuid.uuid4()
    empresa = _make_empresa("Lucky Telecom", eva_account_id=existing_id)
    eva_db = _FakeEvaDB([])
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    # Marks attempted so we don't keep checking
    assert empresa.auto_match_attempted is True
    # Doesn't overwrite the existing link
    assert empresa.eva_account_id == existing_id
    assert eva_db._idx == 0


def test_auto_match_skips_when_eva_db_unavailable():
    empresa = _make_empresa("Lucky Telecom")
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), None, empresa))
    # Did NOT mark attempted — will retry next page load
    assert empresa.auto_match_attempted is False
    assert empresa.eva_account_id is None


def test_auto_match_skips_blank_name():
    empresa = _make_empresa("   ")
    eva_db = _FakeEvaDB([])
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    assert empresa.auto_match_attempted is True
    assert empresa.eva_account_id is None
    assert eva_db._idx == 0


def test_auto_match_links_on_unique_name_match():
    target_id = uuid.uuid4()
    empresa = _make_empresa("Lucky Telecom")
    eva_db = _FakeEvaDB([[target_id]])  # one matching account
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    assert empresa.auto_match_attempted is True
    assert empresa.eva_account_id == target_id


def test_auto_match_skips_on_ambiguous_name_match(caplog):
    a, b = uuid.uuid4(), uuid.uuid4()
    empresa = _make_empresa("Lucky Telecom")
    eva_db = _FakeEvaDB([[a, b]])  # two matching accounts
    with caplog.at_level(logging.INFO, logger="src.empresas.router"):
        asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    assert empresa.auto_match_attempted is True
    assert empresa.eva_account_id is None
    assert any("ambiguous" in r.message for r in caplog.records)


def test_auto_match_skips_on_no_match():
    empresa = _make_empresa("Nonexistent Co")
    eva_db = _FakeEvaDB([[]])  # empty result
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    assert empresa.auto_match_attempted is True
    assert empresa.eva_account_id is None


def test_auto_match_does_not_mark_attempted_on_eva_db_error():
    empresa = _make_empresa("Lucky Telecom")
    eva_db = _FakeEvaDB([RuntimeError("db down")])
    asyncio.run(_attempt_auto_match(_FakeLocalDB(), eva_db, empresa))
    # Did NOT mark attempted — will retry next page load when eva_db
    # is reachable again.
    assert empresa.auto_match_attempted is False
    assert empresa.eva_account_id is None


# ──────────────────────────────────────────────────────────────────────
# _compute_health_for_empresas
# ──────────────────────────────────────────────────────────────────────


def test_compute_health_all_not_linked():
    e1, e2 = uuid.uuid4(), uuid.uuid4()
    eva_db = _FakeEvaDB([])  # never called
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: None, e2: None})
    )
    assert result[e1] == _empty_health("not_linked")
    assert result[e2] == _empty_health("not_linked")
    assert eva_db._idx == 0


def test_compute_health_unknown_when_eva_db_none():
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    result = asyncio.run(
        _compute_health_for_empresas(None, {e1: acc1})
    )
    assert result[e1] == _empty_health("unknown")


def test_compute_health_unknown_when_query_raises():
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    # First eva_db query (account names) raises.
    eva_db = _FakeEvaDB([RuntimeError("connection refused")])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1})
    )
    assert result[e1] == _empty_health("unknown")


def test_compute_health_all_healthy_when_no_unhealthy_rows():
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    # Query order: account names → messenger rows → instagram rows.
    eva_db = _FakeEvaDB([
        [_AccountRow(id=acc1, name="Test Account")],
        [_ChannelRow(is_healthy=True, account_id=acc1)],  # 1 healthy messenger
        [],  # no instagram
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1})
    )
    assert result[e1] == _health(
        "healthy",
        linked_account_name="Test Account",
        msg_present=True,
        msg_healthy=True,
        msg_count=1,
    )


def test_compute_health_unhealthy_when_one_channel_broken():
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    eva_db = _FakeEvaDB([
        [_AccountRow(id=acc1, name="Acc1")],
        [
            _ChannelRow(is_healthy=True, account_id=acc1),
            _ChannelRow(is_healthy=False, account_id=acc1),
        ],
        [],
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1})
    )
    assert result[e1] == _health(
        "unhealthy",
        unhealthy_count=1,
        linked_account_name="Acc1",
        msg_present=True,
        msg_healthy=False,
        msg_count=2,
    )


def test_compute_health_counts_across_messenger_and_instagram():
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    eva_db = _FakeEvaDB([
        [_AccountRow(id=acc1, name="Acc1")],
        [_ChannelRow(is_healthy=False, account_id=acc1)],  # 1 broken messenger
        [
            _ChannelRow(is_healthy=False, account_id=acc1),
            _ChannelRow(is_healthy=True, account_id=acc1),
        ],
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1})
    )
    assert result[e1] == _health(
        "unhealthy",
        unhealthy_count=2,
        linked_account_name="Acc1",
        msg_present=True,
        msg_healthy=False,
        msg_count=1,
        ig_present=True,
        ig_healthy=False,
        ig_count=2,
    )


def test_compute_health_partitions_per_account():
    e1 = uuid.uuid4()
    e2 = uuid.uuid4()
    acc1 = uuid.uuid4()
    acc2 = uuid.uuid4()
    eva_db = _FakeEvaDB([
        [
            _AccountRow(id=acc1, name="Acc1"),
            _AccountRow(id=acc2, name="Acc2"),
        ],
        [
            _ChannelRow(is_healthy=True, account_id=acc1),
            _ChannelRow(is_healthy=False, account_id=acc2),
        ],
        [],
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1, e2: acc2})
    )
    assert result[e1] == _health(
        "healthy",
        linked_account_name="Acc1",
        msg_present=True,
        msg_healthy=True,
        msg_count=1,
    )
    assert result[e2] == _health(
        "unhealthy",
        unhealthy_count=1,
        linked_account_name="Acc2",
        msg_present=True,
        msg_healthy=False,
        msg_count=1,
    )


def test_compute_health_mixed_linked_and_not_linked():
    e1 = uuid.uuid4()
    e2 = uuid.uuid4()
    acc1 = uuid.uuid4()
    eva_db = _FakeEvaDB([
        [_AccountRow(id=acc1, name="Acc1")],
        [_ChannelRow(is_healthy=False, account_id=acc1)],
        [],
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1, e2: None})
    )
    assert result[e1] == _health(
        "unhealthy",
        unhealthy_count=1,
        linked_account_name="Acc1",
        msg_present=True,
        msg_healthy=False,
        msg_count=1,
    )
    assert result[e2] == _empty_health("not_linked")


def test_compute_health_account_with_no_active_channels_is_healthy():
    """An account with zero active channels should be 'healthy' (nothing to break),
    NOT 'not_linked' (which is reserved for empresas with no eva_account_id).
    """
    e1 = uuid.uuid4()
    acc1 = uuid.uuid4()
    eva_db = _FakeEvaDB([
        [_AccountRow(id=acc1, name="Empty Account")],
        [],  # no messenger
        [],  # no instagram
    ])
    result = asyncio.run(
        _compute_health_for_empresas(eva_db, {e1: acc1})
    )
    assert result[e1] == _health(
        "healthy",
        linked_account_name="Empty Account",
    )


# ──────────────────────────────────────────────────────────────────────
# Schema validation
# ──────────────────────────────────────────────────────────────────────


def test_empresa_health_status_literal_validation():
    # Valid statuses
    for status in ("healthy", "unhealthy", "unknown", "not_linked"):
        h = EmpresaHealth(status=status)  # type: ignore[arg-type]
        assert h.status == status
        assert h.unhealthy_count == 0

    # Invalid status raises
    with pytest.raises(Exception):
        EmpresaHealth(status="bogus")  # type: ignore[arg-type]


def test_channel_health_entry_serializes_with_minimal_fields():
    entry = ChannelHealthEntry(
        id=uuid.uuid4(),
        channel_type="messenger",
        display_name="Lucky Telecom",
        is_healthy=True,
        health_status_reason=None,
        last_status_check=None,
    )
    dumped = entry.model_dump()
    assert dumped["channel_type"] == "messenger"
    assert dumped["is_healthy"] is True


def test_account_channel_health_response_groups_by_type():
    acc_id = uuid.uuid4()
    msg = ChannelHealthEntry(
        id=uuid.uuid4(),
        channel_type="messenger",
        display_name="Lucky Telecom",
        is_healthy=True,
        health_status_reason=None,
        last_status_check=None,
    )
    ig = ChannelHealthEntry(
        id=uuid.uuid4(),
        channel_type="instagram",
        display_name="@luckytelecommx",
        is_healthy=False,
        health_status_reason="Token expired",
        last_status_check=datetime.now(timezone.utc),
    )
    response = AccountChannelHealthResponse(
        account_id=acc_id,
        messenger=[msg],
        instagram=[ig],
    )
    assert len(response.messenger) == 1
    assert len(response.instagram) == 1
    assert response.messenger[0].is_healthy is True
    assert response.instagram[0].is_healthy is False
    assert response.instagram[0].health_status_reason == "Token expired"


def test_eva_account_for_link_round_trip():
    acc_id = uuid.uuid4()
    link = EvaAccountForLink(id=acc_id, name="Lucky Telecom")
    dumped = link.model_dump()
    assert dumped["id"] == acc_id
    assert dumped["name"] == "Lucky Telecom"
