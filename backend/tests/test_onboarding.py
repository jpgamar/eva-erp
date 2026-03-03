import asyncio

import pytest

from src.common.config import settings
from src.eva_platform import onboarding
from src.eva_platform.supabase_client import SupabaseAdminError


async def _fake_generate_link(*, email: str, link_type: str = "recovery") -> str:
    assert email
    assert link_type
    return "https://example.com/setup-link"


def test_build_account_onboarding_skips_email_when_disabled(monkeypatch):
    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _fake_generate_link)

    async def _should_not_send(**kwargs):
        raise AssertionError("email sender should not be called when send_setup_email=False")

    monkeypatch.setattr(onboarding, "_send_setup_email", _should_not_send)

    result = asyncio.run(
        onboarding.build_account_onboarding(
            owner_email="owner@example.com",
            owner_name="Owner",
            account_name="Acme",
            send_setup_email=False,
        )
    )

    assert result.email_status == "skipped"
    assert result.onboarding_link == "https://example.com/setup-link"


def test_build_account_onboarding_returns_failed_when_sendgrid_missing(monkeypatch):
    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _fake_generate_link)

    original_key = settings.sendgrid_api_key
    settings.sendgrid_api_key = ""
    try:
        result = asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                account_name="Acme",
                send_setup_email=True,
            )
        )
    finally:
        settings.sendgrid_api_key = original_key

    assert result.email_status == "failed"
    assert "share" in (result.email_message or "").lower()


def test_build_account_onboarding_reports_sent_status(monkeypatch):
    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _fake_generate_link)

    async def _send_success(**kwargs):
        return True, "Setup email sent successfully."

    monkeypatch.setattr(onboarding, "_send_setup_email", _send_success)

    result = asyncio.run(
        onboarding.build_account_onboarding(
            owner_email="owner@example.com",
            owner_name="Owner",
            account_name="Acme",
            send_setup_email=True,
        )
    )

    assert result.email_status == "sent"
    assert result.email_message == "Setup email sent successfully."


def test_build_account_onboarding_raises_when_setup_link_missing(monkeypatch):
    async def _empty_link(**kwargs):
        return ""

    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _empty_link)

    with pytest.raises(SupabaseAdminError):
        asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                account_name="Acme",
                send_setup_email=True,
            )
        )
