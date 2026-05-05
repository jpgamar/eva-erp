from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.empresas.models import Empresa
from src.empresas.router import link_empresa_to_eva_account, router
from src.empresas.schemas import EmpresaItemCreate, EmpresaItemUpdate


def test_calendar_route_is_registered_before_uuid_detail_route():
    paths = [route.path for route in router.routes]
    assert paths.index("/empresas/calendar") < paths.index("/empresas/{empresa_id}")
    assert paths.index("/empresas/link-eva-accounts/auto-match") < paths.index("/empresas/{empresa_id}")


def test_item_create_accepts_followup_dates_and_contact_method():
    payload = EmpresaItemCreate(
        title="Visitar oficina",
        kind="event",
        contact_method="visit",
        due_at=datetime(2026, 5, 12, 15, tzinfo=timezone.utc),
        reminder_at=datetime(2026, 5, 12, 14, tzinfo=timezone.utc),
    )

    assert payload.title == "Visitar oficina"
    assert payload.kind == "event"
    assert payload.contact_method == "visit"
    assert payload.due_at is not None


def test_item_update_rejects_blank_title():
    with pytest.raises(ValueError):
        EmpresaItemUpdate(title="   ")


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeLocalDB:
    def __init__(self, empresa: Empresa, duplicate=None):
        self.empresa = empresa
        self.duplicate = duplicate
        self.flushed = False
        self.refreshed = False
        self.added = []
        self.execute_calls = 0

    async def get(self, model, value):
        assert model is Empresa
        return self.empresa if value == self.empresa.id else None

    async def execute(self, _stmt):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ScalarResult(self.empresa)
        return _ScalarResult(self.duplicate)

    def add(self, _obj):
        self.added.append(_obj)

    async def flush(self):
        self.flushed = True

    async def refresh(self, _obj, attribute_names=None):
        self.refreshed = True


class _FakeEvaDB:
    def __init__(self, account):
        self.account = account

    async def execute(self, _stmt):
        return _ScalarResult(self.account)


class _Account:
    id = uuid4()
    name = "Lucky Telecom"
    stripe_customer_id = "cus_123"
    stripe_subscription_id = "sub_123"
    subscription_status = "ACTIVE"
    current_period_end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    billing_interval = "MONTHLY"


@pytest.mark.asyncio
async def test_link_empresa_to_eva_account_syncs_account_cache():
    account = _Account()
    empresa = Empresa(id=uuid4(), name="Lucky Telecom")
    db = _FakeLocalDB(empresa)

    linked = await link_empresa_to_eva_account(db, _FakeEvaDB(account), empresa.id, account.id)

    assert linked.eva_account_id == account.id
    assert linked.stripe_customer_id == "cus_123"
    assert linked.stripe_subscription_id == "sub_123"
    assert linked.subscription_status == "active"
    assert linked.billing_interval == "monthly"
    assert linked.version == 1
    assert any(getattr(obj, "field_changed", None) == "eva_account_id" for obj in db.added)
    assert db.flushed is True
    assert db.refreshed is True


@pytest.mark.asyncio
async def test_link_empresa_to_eva_account_clears_stale_account_cache():
    class EmptyBillingAccount:
        id = uuid4()
        name = "New Account"
        stripe_customer_id = None
        stripe_subscription_id = None
        subscription_status = None
        current_period_end = None
        billing_interval = None

    empresa = Empresa(
        id=uuid4(),
        name="Lucky Telecom",
        stripe_customer_id="cus_old",
        stripe_subscription_id="sub_old",
        subscription_status="active",
        billing_interval="annual",
    )
    db = _FakeLocalDB(empresa)

    linked = await link_empresa_to_eva_account(db, _FakeEvaDB(EmptyBillingAccount()), empresa.id, EmptyBillingAccount.id)

    assert linked.eva_account_id == EmptyBillingAccount.id
    assert linked.stripe_customer_id is None
    assert linked.stripe_subscription_id is None
    assert linked.subscription_status is None
    assert linked.current_period_end is None
    assert linked.billing_interval == "monthly"
