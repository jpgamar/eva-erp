import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.eva_platform.router import accounts as accounts_router
from src.eva_platform.schemas import (
    EvaBillingCheckoutLinkRequest,
    EvaBillingResendEmailRequest,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def execute(self, *_args, **_kwargs):
        return self._responses.pop(0)


def test_get_account_billing_status_returns_eva_payload(monkeypatch):
    account_id = uuid.uuid4()
    account = SimpleNamespace(id=account_id)
    observed = {}

    async def _fake_get_status(self, requested_account_id):
        observed["account_id"] = requested_account_id
        return {
            "status": {
                "subscription_status": "active",
                "plan_tier": "starter",
                "billing_interval": "monthly",
                "billing_currency": "MXN",
                "current_period_start": None,
                "current_period_end": None,
                "has_active_subscription": True,
                "billing_subscription_cfdi_enabled": True,
                "fiscal_profile_complete": True,
                "retencion_required": False,
                "erp_bridge_enabled_for_retention": True,
                "retencion_on_file": False,
                "usage": {
                    "messages_used": 10,
                    "messages_limit": 500,
                    "agents_used": 1,
                    "agents_limit": 3,
                    "seats_used": 1,
                    "seats_limit": 3,
                },
                "addons": {
                    "extra_agents": 0,
                    "extra_seats": 0,
                    "message_pack_credits": 0,
                },
            },
            "documents": [],
        }

    monkeypatch.setattr(accounts_router.EvaBillingClient, "get_status", _fake_get_status)

    result = asyncio.run(
        accounts_router.get_account_billing_status(
            account_id,
            _FakeSession([_ScalarResult(account)]),
            SimpleNamespace(id=uuid.uuid4()),
        )
    )

    assert str(observed["account_id"]) == str(account_id)
    assert result.status.plan_tier == "starter"


def test_create_account_checkout_link_normalizes_values(monkeypatch):
    account_id = uuid.uuid4()
    account = SimpleNamespace(id=account_id)
    observed = {}

    async def _fake_create_checkout_link(self, **kwargs):
        observed.update(kwargs)
        return {"checkout_url": "https://checkout.stripe.com/pay/test"}

    monkeypatch.setattr(accounts_router.EvaBillingClient, "create_checkout_link", _fake_create_checkout_link)

    result = asyncio.run(
        accounts_router.create_account_checkout_link(
            account_id,
            EvaBillingCheckoutLinkRequest(
                plan_tier="STANDARD",
                billing_interval="MONTHLY",
                billing_subscription_cfdi_enabled=True,
            ),
            _FakeSession([_ScalarResult(account)]),
            SimpleNamespace(id=uuid.uuid4()),
        )
    )

    assert result.checkout_url.startswith("https://checkout.stripe.com")
    assert observed["plan_tier"] == "standard"
    assert observed["billing_interval"] == "monthly"


def test_resend_account_billing_email_uses_service(monkeypatch):
    account_id = uuid.uuid4()
    account = SimpleNamespace(id=account_id)
    observed = {}

    async def _fake_resend(self, db, *, account_id, cfdi_uuid):
        observed["account_id"] = account_id
        observed["cfdi_uuid"] = cfdi_uuid
        return SimpleNamespace(
            status="email_sent",
            email_status="sent",
            cfdi_uuid=cfdi_uuid,
            pdf_url="https://files.example.com/invoice.pdf",
            xml_url="https://files.example.com/invoice.xml",
        )

    monkeypatch.setattr(accounts_router.EvaBillingService, "resend_invoice_email", _fake_resend)

    result = asyncio.run(
        accounts_router.resend_account_billing_email(
            account_id,
            EvaBillingResendEmailRequest(cfdi_uuid="UUID-123"),
            _FakeSession([_ScalarResult(account)]),
            SimpleNamespace(),
            SimpleNamespace(id=uuid.uuid4()),
        )
    )

    assert str(observed["account_id"]) == str(account_id)
    assert observed["cfdi_uuid"] == "UUID-123"
    assert result.email_status == "sent"


def test_create_account_checkout_link_maps_client_errors(monkeypatch):
    account_id = uuid.uuid4()
    account = SimpleNamespace(id=account_id)

    async def _fake_create_checkout_link(self, **_kwargs):
        raise accounts_router.EvaBillingClientError(409, "Active subscription already exists")

    monkeypatch.setattr(accounts_router.EvaBillingClient, "create_checkout_link", _fake_create_checkout_link)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            accounts_router.create_account_checkout_link(
                account_id,
                EvaBillingCheckoutLinkRequest(plan_tier="starter"),
                _FakeSession([_ScalarResult(account)]),
                SimpleNamespace(id=uuid.uuid4()),
            )
        )

    assert exc_info.value.status_code == 409
    assert "active subscription" in str(exc_info.value.detail).lower()
