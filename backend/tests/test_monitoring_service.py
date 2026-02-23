import asyncio

from src.eva_platform.monitoring_service import (
    CheckSpec,
    _run_single_check,
    classify_http_status,
    classify_issue_severity,
    compute_streaks,
)
from src.common.config import settings


class _DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _DummyClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.last_headers: dict[str, str] | None = None

    async def get(self, _target: str, headers: dict[str, str] | None = None) -> _DummyResponse:
        self.last_headers = headers or {}
        return _DummyResponse(self.status_code)


def test_classify_http_status():
    assert classify_http_status(200) == "up"
    assert classify_http_status(302) == "up"
    assert classify_http_status(429) == "degraded"
    assert classify_http_status(500) == "down"


def test_compute_streaks_success_resets_failures():
    failures, successes = compute_streaks(3, 0, "up")
    assert failures == 0
    assert successes == 1


def test_compute_streaks_failure_resets_successes():
    failures, successes = compute_streaks(1, 5, "down")
    assert failures == 2
    assert successes == 0


def test_classify_issue_severity():
    assert classify_issue_severity("down", True) == "critical"
    assert classify_issue_severity("degraded", True) == "high"
    assert classify_issue_severity("down", False) == "high"
    assert classify_issue_severity("degraded", False) == "medium"
    assert classify_issue_severity("up", False) == "low"


def test_supabase_auth_check_requires_key():
    original_monitoring_key = settings.monitoring_supabase_auth_api_key
    original_service_key = settings.supabase_service_role_key
    settings.monitoring_supabase_auth_api_key = ""
    settings.supabase_service_role_key = ""
    spec = CheckSpec(
        check_key="supabase-auth",
        service="Supabase Auth",
        target="https://example.supabase.co/auth/v1/health",
        critical=True,
        category="auth",
        kind="supabase_auth",
    )
    try:
        result = asyncio.run(_run_single_check(_DummyClient(), spec))
        assert result.status == "degraded"
        assert result.error_message is not None
        assert "not configured" in result.error_message
    finally:
        settings.monitoring_supabase_auth_api_key = original_monitoring_key
        settings.supabase_service_role_key = original_service_key


def test_supabase_auth_check_uses_api_key_header():
    original_monitoring_key = settings.monitoring_supabase_auth_api_key
    original_service_key = settings.supabase_service_role_key
    settings.monitoring_supabase_auth_api_key = "sb-monitoring-key"
    settings.supabase_service_role_key = ""
    spec = CheckSpec(
        check_key="supabase-auth",
        service="Supabase Auth",
        target="https://example.supabase.co/auth/v1/health",
        critical=True,
        category="auth",
        kind="supabase_auth",
    )
    try:
        client = _DummyClient(status_code=200)
        result = asyncio.run(_run_single_check(client, spec))
        assert result.status == "up"
        assert client.last_headers is not None
        assert client.last_headers.get("apikey") == "sb-monitoring-key"
        assert client.last_headers.get("Authorization") == "Bearer sb-monitoring-key"
    finally:
        settings.monitoring_supabase_auth_api_key = original_monitoring_key
        settings.supabase_service_role_key = original_service_key


def test_sendgrid_check_requires_key():
    original_sendgrid_key = settings.monitoring_sendgrid_fmac_api_key
    settings.monitoring_sendgrid_fmac_api_key = ""
    spec = CheckSpec(
        check_key="sendgrid-fmac-erp",
        service="SendGrid (FMAccesorios ERP)",
        target="https://api.sendgrid.com/v3/scopes",
        critical=False,
        category="messaging",
        kind="sendgrid",
    )
    try:
        result = asyncio.run(_run_single_check(_DummyClient(), spec))
        assert result.status == "degraded"
        assert result.error_message is not None
        assert "not configured" in result.error_message
    finally:
        settings.monitoring_sendgrid_fmac_api_key = original_sendgrid_key


def test_sendgrid_check_uses_bearer_header():
    original_sendgrid_key = settings.monitoring_sendgrid_fmac_api_key
    settings.monitoring_sendgrid_fmac_api_key = "SG.monitoring-key"
    spec = CheckSpec(
        check_key="sendgrid-fmac-erp",
        service="SendGrid (FMAccesorios ERP)",
        target="https://api.sendgrid.com/v3/scopes",
        critical=False,
        category="messaging",
        kind="sendgrid",
    )
    try:
        client = _DummyClient(status_code=200)
        result = asyncio.run(_run_single_check(client, spec))
        assert result.status == "up"
        assert client.last_headers is not None
        assert client.last_headers.get("Authorization") == "Bearer SG.monitoring-key"
    finally:
        settings.monitoring_sendgrid_fmac_api_key = original_sendgrid_key
