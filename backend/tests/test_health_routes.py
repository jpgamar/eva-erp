from __future__ import annotations

import asyncio

from src import main


def test_health_alias_is_db_free_liveness(monkeypatch):
    async def fail_if_called(*args, **kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("/health must not call database readiness checks")

    monkeypatch.setattr(main, "_db_health", fail_if_called)

    payload = asyncio.run(main.health())

    assert payload["status"] == "ok"
    assert payload["service"] == "eva-erp"
    assert "timestamp" in payload


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
