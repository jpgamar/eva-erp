"""Tests for the empresa <-> Eva account link/create/deactivate rules.

Pure unit tests with fake AsyncSession objects (matching the pattern
in tests/test_empresa_channel_health.py). No Postgres connection.

Coverage maps to the company CRM consolidation plan:
  - link_empresa_to_eva_account syncs cache fields, increments version,
    and writes an EmpresaHistory entry.
  - Stale account cache is cleared when re-pointing to a new account.
  - Linking an empresa whose target account is already linked elsewhere
    surfaces 409.
  - Deactivating an Eva account that's still linked from an empresa is
    blocked with 409.
  - `_preflight_empresa_link` rejects already-linked empresas BEFORE
    Supabase user creation can run (prevents stranded auth users).
"""
from __future__ import annotations

import asyncio
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from src.empresas.models import Empresa
from src.empresas.router import (
    _record_eva_account_link,
    _sync_empresa_from_eva_account,
    link_empresa_to_eva_account,
)
from src.eva_platform.router.accounts import (
    _preflight_empresa_link,
    _record_empresa_link_in_erp,
    deactivate_account,
)


_Row = namedtuple("_Row", ["id", "name"])


def _make_empresa(**overrides: Any) -> Empresa:
    empresa = Empresa(
        id=uuid.uuid4(),
        name="Acme",
        version=3,
        lifecycle_stage="implementacion",
        eva_account_id=None,
        subscription_status=None,
        billing_interval="monthly",
        grandfathered=False,
        auto_match_attempted=False,
        stripe_customer_id="stale",
        stripe_subscription_id="stale-sub",
        current_period_end=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(empresa, key, value)
    return empresa


def _make_account(**overrides: Any) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        name="Eva Account",
        is_active=True,
        stripe_customer_id="cus_new",
        stripe_subscription_id="sub_new",
        subscription_status="active",
        billing_interval="MONTHLY",
        current_period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ── _sync_empresa_from_eva_account / _record_eva_account_link ───────


def test_sync_empresa_from_account_clears_stale_cache_when_pointing_to_new_account() -> None:
    empresa = _make_empresa(
        eva_account_id=uuid.uuid4(),
        stripe_customer_id="stale",
        stripe_subscription_id="stale-sub",
        subscription_status="canceled",
    )
    new_account = _make_account()
    _sync_empresa_from_eva_account(empresa, new_account)
    assert empresa.eva_account_id == new_account.id
    assert empresa.stripe_customer_id == "cus_new"
    assert empresa.stripe_subscription_id == "sub_new"
    assert empresa.subscription_status == "active"
    assert empresa.billing_interval == "monthly"


def test_record_link_appends_history_and_bumps_version() -> None:
    empresa = _make_empresa(version=5)
    account = _make_account()

    captured: list[Any] = []

    class _FakeDb:
        def add(self, obj: Any) -> None:
            captured.append(obj)

    _record_eva_account_link(_FakeDb(), empresa, account, changed_by=uuid.uuid4())  # type: ignore[arg-type]
    assert empresa.version == 6
    history = [c for c in captured if c.__class__.__name__ == "EmpresaHistory"]
    assert len(history) == 1
    assert history[0].field_changed == "eva_account_id"
    assert history[0].new_value == str(account.id)


def test_record_link_skips_history_when_account_unchanged() -> None:
    same_id = uuid.uuid4()
    empresa = _make_empresa(eva_account_id=same_id, version=2)
    account = _make_account(id=same_id)
    captured: list[Any] = []

    class _FakeDb:
        def add(self, obj: Any) -> None:
            captured.append(obj)

    _record_eva_account_link(_FakeDb(), empresa, account, changed_by=None)  # type: ignore[arg-type]
    history = [c for c in captured if c.__class__.__name__ == "EmpresaHistory"]
    assert history == []
    assert empresa.version == 2  # unchanged


# ── link_empresa_to_eva_account end-to-end (faked sessions) ─────────


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeDb:
    def __init__(self, empresa: Empresa, *, duplicate_check: Any | None = None) -> None:
        self._empresa = empresa
        self._duplicate_check = duplicate_check
        self.added: list[Any] = []
        self._exec_calls = 0

    async def execute(self, _query: Any) -> _ScalarResult:
        self._exec_calls += 1
        if self._exec_calls == 1:
            return _ScalarResult(self._empresa)
        # Subsequent calls hit the duplicate check
        return _ScalarResult(self._duplicate_check)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def refresh(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeEvaDb:
    def __init__(self, account: Any | None) -> None:
        self._account = account

    async def execute(self, _query: Any) -> _ScalarResult:
        return _ScalarResult(self._account)


def test_link_empresa_409_when_account_already_linked_elsewhere() -> None:
    empresa = _make_empresa()
    db = _FakeDb(empresa, duplicate_check=uuid.uuid4())
    eva_db = _FakeEvaDb(_make_account())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            link_empresa_to_eva_account(db, eva_db, empresa.id, uuid.uuid4(), changed_by=None)  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "already_linked"


def test_link_empresa_409_when_already_linked_to_another_account() -> None:
    empresa = _make_empresa(eva_account_id=uuid.uuid4())
    db = _FakeDb(empresa)
    eva_db = _FakeEvaDb(_make_account())
    new_target = uuid.uuid4()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            link_empresa_to_eva_account(db, eva_db, empresa.id, new_target, changed_by=None)  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "empresa_already_linked"


def test_link_empresa_404_when_account_missing() -> None:
    empresa = _make_empresa()
    db = _FakeDb(empresa)
    eva_db = _FakeEvaDb(None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            link_empresa_to_eva_account(db, eva_db, empresa.id, uuid.uuid4(), changed_by=None)  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


def test_link_empresa_409_when_account_inactive() -> None:
    empresa = _make_empresa()
    db = _FakeDb(empresa)
    eva_db = _FakeEvaDb(_make_account(is_active=False))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            link_empresa_to_eva_account(db, eva_db, empresa.id, uuid.uuid4(), changed_by=None)  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "account_inactive"


def test_link_empresa_409_on_optimistic_version_mismatch() -> None:
    empresa = _make_empresa(version=4)
    db = _FakeDb(empresa)
    eva_db = _FakeEvaDb(_make_account())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            link_empresa_to_eva_account(
                db, eva_db, empresa.id, uuid.uuid4(), changed_by=None, expected_version=2
            )  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "OptimisticLockMismatch"


def test_link_empresa_success_path_syncs_cache_and_history() -> None:
    empresa = _make_empresa()
    db = _FakeDb(empresa)
    account = _make_account()
    eva_db = _FakeEvaDb(account)

    result = asyncio.run(
        link_empresa_to_eva_account(db, eva_db, empresa.id, account.id, changed_by=uuid.uuid4())  # type: ignore[arg-type]
    )
    assert result is empresa
    assert empresa.eva_account_id == account.id
    assert empresa.subscription_status == "active"
    history = [obj for obj in db.added if obj.__class__.__name__ == "EmpresaHistory"]
    assert len(history) == 1


# ── _preflight_empresa_link (fail BEFORE Supabase) ──────────────────


def test_preflight_returns_empresa_when_unlinked() -> None:
    empresa = _make_empresa()

    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(empresa)

    result = asyncio.run(_preflight_empresa_link(_Db(), empresa.id))  # type: ignore[arg-type]
    assert result is empresa


def test_preflight_404_when_empresa_missing() -> None:
    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_preflight_empresa_link(_Db(), uuid.uuid4()))  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_preflight_409_when_already_linked() -> None:
    empresa = _make_empresa(eva_account_id=uuid.uuid4())

    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(empresa)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_preflight_empresa_link(_Db(), empresa.id))  # type: ignore[arg-type]
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "empresa_already_linked"


def test_record_empresa_link_in_erp_clears_stale_cache_and_bumps_version() -> None:
    empresa = _make_empresa(
        eva_account_id=uuid.uuid4(),
        stripe_customer_id="stale",
        stripe_subscription_id="stale-sub",
        subscription_status="canceled",
        version=10,
    )
    account = _make_account()
    captured: list[Any] = []

    class _Db:
        def add(self, obj: Any) -> None:
            captured.append(obj)

    _record_empresa_link_in_erp(_Db(), empresa, account, changed_by=uuid.uuid4())  # type: ignore[arg-type]
    assert empresa.version == 11
    assert empresa.eva_account_id == account.id
    # Fresh account has no Stripe sub yet — clear all the legacy cache.
    assert empresa.stripe_customer_id is None
    assert empresa.stripe_subscription_id is None
    assert empresa.subscription_status is None
    history = [c for c in captured if c.__class__.__name__ == "EmpresaHistory"]
    assert len(history) == 1


# ── deactivate_account: blocks when empresa link exists ─────────────


class _ActiveAccount:
    def __init__(self, account_id: uuid.UUID) -> None:
        self.id = account_id
        self.name = "Eva Acme"
        self.is_active = True
        self.updated_at: datetime | None = None


class _EvaDb:
    def __init__(self, account: _ActiveAccount) -> None:
        self._account = account
        self.added: list[Any] = []

    async def execute(self, _q: Any) -> _ScalarResult:
        return _ScalarResult(self._account)

    def add(self, obj: Any) -> None:
        self.added.append(obj)


class _DbLinkedRow:
    def __init__(self, row: Any | None) -> None:
        self._row = row

    def first(self) -> Any | None:
        return self._row


class _DbWithLink:
    def __init__(self, link_row: Any | None) -> None:
        self._link_row = link_row

    async def execute(self, _q: Any) -> _DbLinkedRow:
        return _DbLinkedRow(self._link_row)


def test_deactivate_blocked_when_empresa_link_exists() -> None:
    account_id = uuid.uuid4()
    account = _ActiveAccount(account_id)
    eva_db = _EvaDb(account)
    db = _DbWithLink(_Row(uuid.uuid4(), "Acme"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            deactivate_account(account_id, eva_db=eva_db, user=SimpleNamespace(id=uuid.uuid4()), db=db)  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "empresa_link_exists"
    assert account.is_active is True  # untouched


def test_deactivate_succeeds_when_no_empresa_link() -> None:
    account_id = uuid.uuid4()
    account = _ActiveAccount(account_id)
    eva_db = _EvaDb(account)
    db = _DbWithLink(None)

    asyncio.run(
        deactivate_account(account_id, eva_db=eva_db, user=SimpleNamespace(id=uuid.uuid4()), db=db)  # type: ignore[arg-type]
    )
    assert account.is_active is False
    assert account in eva_db.added


# ── Pre-Supabase fail-fast for operativo empresas ───────────────────


def test_preflight_409_when_empresa_operativo_and_unlinked() -> None:
    empresa = _make_empresa(lifecycle_stage="operativo", grandfathered=False)

    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(empresa)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_preflight_empresa_link(_Db(), empresa.id))  # type: ignore[arg-type]
    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "OperativoRequiresExistingSubscription"


def test_preflight_allows_grandfathered_operativo() -> None:
    empresa = _make_empresa(lifecycle_stage="operativo", grandfathered=True)

    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(empresa)

    result = asyncio.run(_preflight_empresa_link(_Db(), empresa.id))  # type: ignore[arg-type]
    assert result is empresa


def test_create_account_for_operativo_empresa_does_not_call_supabase() -> None:
    """Regression: a fresh-account create from an operativo empresa must
    fail before any Supabase admin call. We assert by patching the
    Supabase admin and confirming it was never invoked.
    """
    from unittest.mock import AsyncMock, patch

    from src.empresas.router import create_eva_account_for_empresa
    from src.empresas.schemas import CreateEvaAccountForEmpresaRequest

    empresa = _make_empresa(lifecycle_stage="operativo", grandfathered=False)

    class _Db:
        async def execute(self, _q: Any) -> _ScalarResult:
            return _ScalarResult(empresa)

    payload = CreateEvaAccountForEmpresaRequest(owner_email="x@example.com")
    with patch(
        "src.eva_platform.supabase_client.SupabaseAdminClient.admin_create_user",
        new_callable=AsyncMock,
    ) as supabase_mock:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                create_eva_account_for_empresa(
                    empresa_id=empresa.id,
                    payload=payload,
                    db=_Db(),  # type: ignore[arg-type]
                    eva_db=_Db(),  # type: ignore[arg-type]
                    user=SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
                )
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["reason"] == "OperativoRequiresExistingSubscription"
        supabase_mock.assert_not_called()
