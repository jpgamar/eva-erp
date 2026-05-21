from __future__ import annotations

import asyncio

import pytest

from src import main


def test_health_alias_is_db_free_liveness(monkeypatch):
    async def fail_if_called(*args, **kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("/health must not call database readiness checks")

    monkeypatch.setattr(main, "_db_health", fail_if_called)

    payload = asyncio.run(main.health())

    assert payload["status"] == "ok"
    assert payload["service"] == "eva-erp"
    assert "timestamp" in payload


def test_readiness_does_not_call_run_live_checks(monkeypatch):
    """Regression for the 2026-05-21 FacturAPI runaway.

    The readiness endpoint MUST NOT fan out to external monitoring checks.
    It used to call `run_live_checks` which, combined with the `erp-api`
    spec that pointed at /health/readiness itself, produced a doubling
    reflection loop hammering FacturAPI 14,799 times per day.
    """
    async def fake_db_health(timeout_seconds: float = 2.0):
        return True, None, True, None

    async def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "/health/readiness must not call run_live_checks — external "
            "API polling is the background monitor's job, not readiness's."
        )

    monkeypatch.setattr(main, "_db_health", fake_db_health)
    # Even if run_live_checks were re-imported, calling it should explode.
    import src.eva_platform.monitoring_service as monitoring_service

    monkeypatch.setattr(monitoring_service, "run_live_checks", fail_if_called)

    payload = asyncio.run(main.health_readiness())
    # If readiness returned JSONResponse (failure path) the test still
    # short-circuits because fake_db_health says everything is up.
    assert payload["status"] == "ok"
    assert payload["service"] == "eva-erp"
    assert payload["erp_db_connected"] is True


def test_readiness_returns_503_when_db_down(monkeypatch):
    async def fake_db_health(timeout_seconds: float = 2.0):
        return False, "connection refused", False, "connection refused"

    monkeypatch.setattr(main, "_db_health", fake_db_health)

    response = asyncio.run(main.health_readiness())
    # JSONResponse object — pull its status_code attribute.
    assert getattr(response, "status_code", None) == 503


def test_db_health_check_times_out_instead_of_hanging():
    class _SlowConnection:
        async def __aenter__(self):
            await asyncio.sleep(0.2)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def execute(self, _statement):
            return None

    class _SlowEngine:
        def connect(self):
            return _SlowConnection()

    ok, error = asyncio.run(
        main._check_db_connection(
            _SlowEngine(),
            "ERP database",
            timeout_seconds=0.1,
        )
    )

    assert ok is False
    assert error == "ERP database health check timed out after 0.1s"
