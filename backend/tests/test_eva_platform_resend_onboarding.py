import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.eva_platform.router import accounts as accounts_router
from src.eva_platform.schemas import AccountOnboardingResponse, ResendAccountOnboardingRequest


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _UsersResult:
    def __init__(self, users):
        self._users = users

    def scalars(self):
        return self

    def all(self):
        return self._users


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def execute(self, *_args, **_kwargs):
        return self._responses.pop(0)


def test_resend_account_onboarding_uses_owner_candidate(monkeypatch):
    account_id = uuid.uuid4()
    account = SimpleNamespace(
        id=account_id,
        owner_user_id="owner-user-id",
        account_type="COMMERCE",
    )
    users = [
        SimpleNamespace(
            user_id="owner-user-id",
            email="OWNER@EXAMPLE.COM",
            display_name="Owner Name",
            role="OWNER",
            status="ACTIVE",
        ),
    ]
    fake_db = _FakeSession([_ScalarResult(account), _UsersResult(users)])
    observed = {}

    async def _fake_build_account_onboarding(**kwargs):
        observed.update(kwargs)
        return AccountOnboardingResponse(
            owner_email=kwargs["owner_email"],
            onboarding_link="https://example.com/setup-link",
            email_status="sent",
            email_message="ok",
        )

    monkeypatch.setattr(accounts_router, "build_account_onboarding", _fake_build_account_onboarding)

    result = asyncio.run(
        accounts_router.resend_account_onboarding(
            account_id,
            ResendAccountOnboardingRequest(send_setup_email=True),
            fake_db,
            SimpleNamespace(id=uuid.uuid4()),
        )
    )

    assert result.email_status == "sent"
    assert observed["owner_email"] == "owner@example.com"
    assert observed["owner_name"] == "Owner Name"
    assert observed["product_label"] == "Eva Commerce"
    assert observed["send_setup_email"] is True


def test_resend_account_onboarding_requires_owner_candidate():
    account_id = uuid.uuid4()
    account = SimpleNamespace(
        id=account_id,
        owner_user_id="owner-user-id",
        account_type="COMMERCE",
    )
    users = [
        SimpleNamespace(
            user_id="member-id",
            email="member@example.com",
            display_name="Member",
            role="MEMBER",
            status="ACTIVE",
        ),
    ]
    fake_db = _FakeSession([_ScalarResult(account), _UsersResult(users)])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            accounts_router.resend_account_onboarding(
                account_id,
                ResendAccountOnboardingRequest(send_setup_email=True),
                fake_db,
                SimpleNamespace(id=uuid.uuid4()),
            )
        )

    assert exc_info.value.status_code == 404
    assert "owner user" in str(exc_info.value.detail).lower()
