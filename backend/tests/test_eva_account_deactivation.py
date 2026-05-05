from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.eva_platform.router.accounts import create_account, deactivate_account
from src.eva_platform.schemas import EvaAccountCreateRequest


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeEvaDB:
    def __init__(self, account):
        self.account = account
        self.added = []

    async def execute(self, _stmt):
        return _ScalarResult(self.account)

    def add(self, obj):
        self.added.append(obj)


class _FakeERPDB:
    def __init__(self, linked_empresa_id=None):
        self.linked_empresa_id = linked_empresa_id

    async def execute(self, _stmt):
        return _ScalarResult(self.linked_empresa_id)


class _FakeEmpresaDB:
    def __init__(self, empresa):
        self.empresa = empresa

    async def execute(self, _stmt):
        return _ScalarResult(self.empresa)


@pytest.mark.asyncio
async def test_deactivate_account_blocks_when_linked_to_empresa():
    account_id = uuid4()
    account = SimpleNamespace(id=account_id, name="Lucky Telecom", is_active=True, updated_at=None)

    with pytest.raises(HTTPException) as exc:
        await deactivate_account(
            account_id,
            db=_FakeERPDB(linked_empresa_id=uuid4()),
            eva_db=_FakeEvaDB(account),
            user=SimpleNamespace(id=uuid4()),
        )

    assert exc.value.status_code == 409
    assert "linked to an Empresa" in exc.value.detail
    assert account.is_active is True


@pytest.mark.asyncio
async def test_deactivate_account_allows_unlinked_account():
    account_id = uuid4()
    account = SimpleNamespace(id=account_id, name="Lucky Telecom", is_active=True, updated_at=None)
    eva_db = _FakeEvaDB(account)

    result = await deactivate_account(
        account_id,
        db=_FakeERPDB(),
        eva_db=eva_db,
        user=SimpleNamespace(id=uuid4()),
    )

    assert result == {"message": "Account 'Lucky Telecom' deactivated"}
    assert account.is_active is False
    assert account.updated_at is not None
    assert eva_db.added == [account]


@pytest.mark.asyncio
async def test_create_account_blocks_operativo_empresa_before_supabase(monkeypatch):
    calls = []

    async def _admin_create_user(**_kwargs):
        calls.append("supabase")
        return {"id": str(uuid4()), "email": "owner@example.com"}

    monkeypatch.setattr(
        "src.eva_platform.router.accounts.SupabaseAdminClient.admin_create_user",
        _admin_create_user,
    )
    empresa = SimpleNamespace(
        id=uuid4(),
        eva_account_id=None,
        lifecycle_stage="operativo",
        grandfathered=False,
    )

    with pytest.raises(HTTPException) as exc:
        await create_account(
            EvaAccountCreateRequest(
                name="Lucky Telecom",
                owner_email="owner@example.com",
                owner_name="Owner",
                empresa_id=empresa.id,
            ),
            db=_FakeEmpresaDB(empresa),
            eva_db=SimpleNamespace(),
            user=SimpleNamespace(id=uuid4()),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["reason"] == "OperativoRequiresActiveSubscription"
    assert calls == []
