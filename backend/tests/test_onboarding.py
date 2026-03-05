import asyncio

import pytest

from src.common.config import settings
from src.eva_platform import onboarding
from src.eva_platform.supabase_client import SupabaseAdminError


async def _fake_generate_link(
    *,
    email: str,
    link_type: str = "recovery",
    redirect_to: str | None = None,
) -> str:
    assert email
    assert link_type
    assert redirect_to
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
            product_label="Eva Commerce",
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
                product_label="Eva Commerce",
                send_setup_email=True,
            )
        )
    finally:
        settings.sendgrid_api_key = original_key

    assert result.email_status == "failed"
    assert "sendgrid not configured" in (result.email_message or "").lower()


def test_build_account_onboarding_returns_failed_when_sendgrid_raises(monkeypatch):
    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _fake_generate_link)
    class DummyClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            raise RuntimeError("network down")

    monkeypatch.setattr(onboarding.httpx, "AsyncClient", DummyClient)

    original_key = settings.sendgrid_api_key
    settings.sendgrid_api_key = "SG.test"
    try:
        result = asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                product_label="Eva Commerce",
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
            product_label="Eva Commerce",
            send_setup_email=True,
        )
    )

    assert result.email_status == "sent"
    assert result.email_message == "Setup email sent successfully."


def test_build_account_onboarding_passes_redirect_to_supabase(monkeypatch):
    observed: dict[str, str | None] = {"redirect_to": None}

    async def _capture_generate_link(*, email: str, link_type: str = "recovery", redirect_to: str | None = None):
        observed["redirect_to"] = redirect_to
        return "https://example.com/setup-link"

    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _capture_generate_link)

    async def _send_success(**kwargs):
        return True, "ok"

    monkeypatch.setattr(onboarding, "_send_setup_email", _send_success)

    result = asyncio.run(
        onboarding.build_account_onboarding(
            owner_email="owner@example.com",
            owner_name="Owner",
            product_label="Eva Commerce",
            send_setup_email=True,
        )
    )

    assert result.onboarding_link == "https://example.com/setup-link"
    assert observed["redirect_to"] == onboarding._resolve_onboarding_redirect_url(
        settings.eva_app_onboarding_redirect_url
    )


def test_build_account_onboarding_normalizes_login_redirect_to_change_password(monkeypatch):
    observed: dict[str, str | None] = {"redirect_to": None}

    async def _capture_generate_link(*, email: str, link_type: str = "recovery", redirect_to: str | None = None):
        observed["redirect_to"] = redirect_to
        return "https://example.com/setup-link"

    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _capture_generate_link)

    async def _send_success(**kwargs):
        return True, "ok"

    monkeypatch.setattr(onboarding, "_send_setup_email", _send_success)

    original_redirect = settings.eva_app_onboarding_redirect_url
    settings.eva_app_onboarding_redirect_url = "https://app.goeva.ai/login?redirect=%2Fdashboard"
    try:
        result = asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                product_label="Eva Commerce",
                send_setup_email=True,
            )
        )
    finally:
        settings.eva_app_onboarding_redirect_url = original_redirect

    assert result.onboarding_link == "https://example.com/setup-link"
    assert observed["redirect_to"] == "https://app.goeva.ai/auth/change-password"


def test_build_account_onboarding_uses_change_password_default_when_redirect_missing(monkeypatch):
    observed: dict[str, str | None] = {"redirect_to": None}

    async def _capture_generate_link(*, email: str, link_type: str = "recovery", redirect_to: str | None = None):
        observed["redirect_to"] = redirect_to
        return "https://example.com/setup-link"

    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _capture_generate_link)

    async def _send_success(**kwargs):
        return True, "ok"

    monkeypatch.setattr(onboarding, "_send_setup_email", _send_success)

    original_redirect = settings.eva_app_onboarding_redirect_url
    settings.eva_app_onboarding_redirect_url = ""
    try:
        result = asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                product_label="Eva Commerce",
                send_setup_email=True,
            )
        )
    finally:
        settings.eva_app_onboarding_redirect_url = original_redirect

    assert result.onboarding_link == "https://example.com/setup-link"
    assert observed["redirect_to"] == "https://app.goeva.ai/auth/change-password"


def test_build_account_onboarding_raises_when_setup_link_missing(monkeypatch):
    async def _empty_link(**kwargs):
        return ""

    monkeypatch.setattr(onboarding.SupabaseAdminClient, "admin_generate_link", _empty_link)

    with pytest.raises(SupabaseAdminError):
        asyncio.run(
            onboarding.build_account_onboarding(
                owner_email="owner@example.com",
                owner_name="Owner",
                product_label="Eva Commerce",
                send_setup_email=True,
            )
        )


def test_send_setup_email_uses_branding_and_reply_to(monkeypatch):
    class DummyResponse:
        status_code = 202
        text = ""

    captured = {}

    class DummyClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["json"] = json or {}
            return DummyResponse()

    monkeypatch.setattr(onboarding.httpx, "AsyncClient", DummyClient)

    original_api_key = settings.sendgrid_api_key
    original_from_email = settings.sendgrid_from_email
    original_from_name = settings.sendgrid_from_name
    original_reply_to = settings.sendgrid_reply_to
    settings.sendgrid_api_key = "SG.test"
    settings.sendgrid_from_email = "no-reply@goeva.ai"
    settings.sendgrid_from_name = "Eva ERP"
    settings.sendgrid_reply_to = "hi@goeva.ai"
    try:
        ok, message = asyncio.run(
            onboarding._send_setup_email(
                owner_email="owner@example.com",
                owner_name="Owner",
                product_label="Eva Commerce",
                onboarding_link="https://example.com/setup-link",
            )
        )
    finally:
        settings.sendgrid_api_key = original_api_key
        settings.sendgrid_from_email = original_from_email
        settings.sendgrid_from_name = original_from_name
        settings.sendgrid_reply_to = original_reply_to

    assert ok is True
    assert "successfully" in message.lower()
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert captured["json"]["from"]["email"] == "no-reply@goeva.ai"
    assert captured["json"]["from"]["name"] == "Eva ERP"
    assert captured["json"]["reply_to"]["email"] == "hi@goeva.ai"
    assert captured["json"]["personalizations"][0]["subject"] == "Configura tu contrasena para Eva Commerce"
    assert captured["json"]["tracking_settings"]["click_tracking"]["enable"] is False
    text = captured["json"]["content"][0]["value"]
    assert "Usa este enlace seguro para definir tu contrasena y terminar la configuracion" not in text
    assert "Si el enlace expira" not in text
    html = captured["json"]["content"][1]["value"]
    assert "<img" not in html
    assert "Eva Commerce" in html
    assert "<svg" not in html
    assert "EvaAI" in html
    assert "Configurar contrasena" in html
    assert "Si el boton no abre, copia y pega este enlace en tu navegador" not in html
    assert "word-break:break-all" not in html
    assert "Usa este enlace seguro para definir tu contrasena y terminar la configuracion" not in html
    assert "Si el enlace expira" not in html
