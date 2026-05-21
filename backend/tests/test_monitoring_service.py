import asyncio

import httpx

import src.eva_platform.monitoring_service as monitoring_service
from src.eva_platform.monitoring_service import (
    CIRCUIT_BREAKER_MAX_PER_HOUR,
    CheckSpec,
    _build_check_specs,
    _dedupe_facturapi_specs_by_api_key,
    _run_single_check,
    classify_http_status,
    classify_issue_severity,
    compute_streaks,
    reset_monitoring_throttles,
    run_live_checks,
)
from src.common.config import settings


class _DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _DummyClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.last_headers: dict[str, str] | None = None
        self.calls = 0

    async def get(
        self,
        _target: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _DummyResponse:
        self.calls += 1
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


def test_sendgrid_check_uses_fmac_health_endpoint():
    spec = CheckSpec(
        check_key="sendgrid-fmac-erp",
        service="SendGrid (FMAccesorios ERP)",
        target="https://erp.fmaccesorios.com/api/v1/health/sendgrid",
        critical=False,
        category="messaging",
        kind="http",
        success_statuses=(200,),
    )
    client = _DummyClient(status_code=200)
    result = asyncio.run(_run_single_check(client, spec))
    assert result.status == "up"


def test_http_check_retries_transient_timeout():
    class _FlakyClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get(
            self,
            _target: str,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
        ) -> _DummyResponse:
            self.calls += 1
            if self.calls == 1:
                raise httpx.ReadTimeout("timed out")
            return _DummyResponse(200)

    spec = CheckSpec(
        check_key="retry-check",
        service="Retry Check",
        target="https://example.com/health",
        critical=True,
        category="api",
    )
    client = _FlakyClient()
    result = asyncio.run(_run_single_check(client, spec))
    assert result.status == "up"
    assert result.http_status == 200
    assert client.calls == 2


def test_http_check_timeout_error_is_never_blank():
    class _TimeoutClient:
        async def get(
            self,
            _target: str,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
        ) -> _DummyResponse:
            raise httpx.ReadTimeout("")

    spec = CheckSpec(
        check_key="timeout-check",
        service="Timeout Check",
        target="https://example.com/health",
        critical=True,
        category="api",
    )
    result = asyncio.run(_run_single_check(_TimeoutClient(), spec))
    assert result.status == "down"
    assert result.error_message is not None
    assert "ReadTimeout" in result.error_message


def test_http_check_honors_custom_retry_attempts():
    class _FlakyClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get(
            self,
            _target: str,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
        ) -> _DummyResponse:
            self.calls += 1
            if self.calls < 3:
                raise httpx.ReadTimeout("timed out")
            return _DummyResponse(200)

    spec = CheckSpec(
        check_key="retry-check-custom",
        service="Retry Check Custom",
        target="https://example.com/health",
        critical=True,
        category="api",
        retry_attempts=3,
    )
    client = _FlakyClient()
    result = asyncio.run(_run_single_check(client, spec))
    assert result.status == "up"
    assert client.calls == 3


# ── Regression tests for the 2026-05-21 FacturAPI runaway ─────────────


def test_no_erp_api_self_check_spec():
    """The erp-api spec used to target /health/readiness, which itself
    called run_live_checks — producing a reflection loop that doubled
    every external monitoring call (the proximate cause of the 14,799/day
    FacturAPI loop). It must never come back."""
    specs = _build_check_specs()
    assert all(spec.check_key != "erp-api" for spec in specs), (
        "erp-api self-check is forbidden: it points at /health/readiness "
        "which used to run_live_checks → infinite reflection loop"
    )


def test_dedupe_facturapi_specs_with_same_api_key():
    """When the per-target FacturAPI monitoring keys are unset they all
    fall back to settings.facturapi_api_key. Three specs pointing at the
    same FacturAPI org would triple-hit it on every cycle. The dedupe
    pass must collapse them down to one."""
    shared_key = "sk_live_shared"
    specs = [
        CheckSpec(check_key="facturapi-a", service="A", target="x", critical=False,
                  category="billing", kind="facturapi", api_key=shared_key),
        CheckSpec(check_key="facturapi-b", service="B", target="x", critical=False,
                  category="billing", kind="facturapi", api_key=shared_key),
        CheckSpec(check_key="facturapi-c", service="C", target="x", critical=False,
                  category="billing", kind="facturapi", api_key=shared_key),
    ]
    deduped = _dedupe_facturapi_specs_by_api_key(specs)
    assert len(deduped) == 1
    assert deduped[0].check_key == "facturapi-a"


def test_dedupe_keeps_distinct_facturapi_keys():
    """Distinct API keys = distinct FacturAPI organizations. Both must run."""
    specs = [
        CheckSpec(check_key="facturapi-a", service="A", target="x", critical=False,
                  category="billing", kind="facturapi", api_key="sk_live_one"),
        CheckSpec(check_key="facturapi-b", service="B", target="x", critical=False,
                  category="billing", kind="facturapi", api_key="sk_live_two"),
    ]
    deduped = _dedupe_facturapi_specs_by_api_key(specs)
    assert len(deduped) == 2


def test_dedupe_only_touches_facturapi_kind():
    """Dedupe is FacturAPI-specific. Other kinds (http/openai/sendgrid/db)
    must be left alone."""
    specs = [
        CheckSpec(check_key="openai-1", service="O1", target="x", critical=False,
                  category="ai", kind="openai", api_key="sk_shared"),
        CheckSpec(check_key="sendgrid-1", service="S1", target="x", critical=False,
                  category="messaging", kind="sendgrid", api_key="sk_shared"),
        CheckSpec(check_key="http-1", service="H1", target="x", critical=False,
                  category="api", kind="http"),
    ]
    deduped = _dedupe_facturapi_specs_by_api_key(specs)
    assert len(deduped) == 3


def test_min_interval_skips_second_call_within_window(monkeypatch):
    """A spec with min_interval_seconds=600 must NOT fire a real HTTP
    request a second time inside the same 10-minute window. The second
    call returns the cached result instead."""
    reset_monitoring_throttles()
    call_count = {"n": 0}

    async def fake_single(client, spec):
        call_count["n"] += 1
        return monitoring_service.CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="up",
            critical=spec.critical,
            category=spec.category,
            checked_at=monitoring_service._now_utc(),
            http_status=200,
        )

    monkeypatch.setattr(monitoring_service, "_run_single_check", fake_single)
    monkeypatch.setattr(
        monitoring_service,
        "_build_check_specs",
        lambda: [
            CheckSpec(
                check_key="throttled-x",
                service="X",
                target="https://example.com",
                critical=False,
                category="billing",
                kind="http",
                min_interval_seconds=600,
            )
        ],
    )

    first = asyncio.run(run_live_checks())
    second = asyncio.run(run_live_checks())

    assert call_count["n"] == 1
    assert len(first) == 1 and len(second) == 1
    assert first[0].check_key == second[0].check_key == "throttled-x"


def test_circuit_breaker_blocks_after_hourly_cap(monkeypatch):
    """Even if min_interval is misconfigured to 0 (always run), the
    rolling-hour circuit breaker must short-circuit after
    CIRCUIT_BREAKER_MAX_PER_HOUR live invocations and return cached
    results instead of additional HTTP calls."""
    reset_monitoring_throttles()
    call_count = {"n": 0}

    async def fake_single(client, spec):
        call_count["n"] += 1
        return monitoring_service.CheckResult(
            check_key=spec.check_key,
            service=spec.service,
            target=spec.target,
            status="up",
            critical=spec.critical,
            category=spec.category,
            checked_at=monitoring_service._now_utc(),
            http_status=200,
        )

    monkeypatch.setattr(monitoring_service, "_run_single_check", fake_single)
    monkeypatch.setattr(
        monitoring_service,
        "_build_check_specs",
        lambda: [
            CheckSpec(
                check_key="runaway-y",
                service="Y",
                target="https://example.com",
                critical=False,
                category="billing",
                kind="http",
                # min_interval=0 means the throttle won't catch this; we're
                # explicitly testing the hourly cap is the last line of
                # defense.
                min_interval_seconds=0,
            )
        ],
    )

    # Fire well past the hourly cap.
    for _ in range(CIRCUIT_BREAKER_MAX_PER_HOUR + 50):
        asyncio.run(run_live_checks())

    # Real HTTP calls cap at exactly CIRCUIT_BREAKER_MAX_PER_HOUR.
    assert call_count["n"] == CIRCUIT_BREAKER_MAX_PER_HOUR
