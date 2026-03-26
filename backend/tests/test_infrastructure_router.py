import uuid
from types import SimpleNamespace
import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

if "jose" not in sys.modules:
    sys.modules["jose"] = types.SimpleNamespace(jwt=types.SimpleNamespace())
if "passlib.context" not in sys.modules:
    class _DummyCryptContext:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            _ = (args, kwargs)

        def hash(self, value: str) -> str:
            return value

        def verify(self, plain: str, hashed: str) -> bool:
            return plain == hashed

    sys.modules["passlib"] = types.ModuleType("passlib")
    sys.modules["passlib.context"] = types.SimpleNamespace(CryptContext=_DummyCryptContext)
if "asyncssh" not in sys.modules:
    sys.modules["asyncssh"] = types.SimpleNamespace(
        SSHClientConnection=object,
        connect=lambda *args, **kwargs: None,
    )

from src.eva_platform.eva_api_client import eva_admin_api_client
from src.eva_platform.router.infrastructure import get_current_user
from src.eva_platform.router.infrastructure import router as infrastructure_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(infrastructure_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4(), role="admin")
    return TestClient(app)


def test_openclaw_overview_proxy_returns_monitoring_and_fleet_audit(monkeypatch):
    async def fake_request(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        if method == "GET" and path == "/openclaw/admin/runtime/monitoring/overview":
            return {
                "slots_available": 2,
                "active_hosts": 1,
                "warning_hosts": 0,
                "critical_hosts": 0,
                "queue_depth": 0,
                "locked_tenants": 0,
                "release_parity_status": "ok",
                "release_parity": {"status": "ok"},
                "release_drift_count": 1,
                "readiness_drift_count": 0,
                "manual_interventions_24h": 1,
                "hosts": [],
                "allocations": [],
                "incidents": [],
            }
        if method == "GET" and path == "/openclaw/admin/runtime/fleet-audit":
            return {
                "checked_at": "2026-03-26T00:00:00Z",
                "total_employees": 1,
                "reprovision_recommended_count": 1,
                "release_drift_count": 1,
                "readiness_drift_count": 0,
                "token_drift_count": 0,
                "suspected_untracked_change_count": 1,
                "employees": [],
            }
        raise AssertionError(f"Unexpected proxy call: {method} {path}")

    monkeypatch.setattr(eva_admin_api_client, "request", fake_request)
    client = _build_client()

    response = client.get("/infrastructure/openclaw/overview")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["monitoring"]["release_parity_status"] == "ok"
    assert payload["fleet_audit"]["reprovision_recommended_count"] == 1
    assert payload["fleet_audit"]["suspected_untracked_change_count"] == 1


def test_openclaw_employee_actions_proxy_to_eva(monkeypatch):
    employee_id = uuid.uuid4()
    calls: list[tuple[str, str, dict]] = []

    async def fake_request(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs))
        if path.endswith("/run-checks"):
            return {
                "accepted": True,
                "message": "Readiness checks passed and the employee is ready to chat.",
            }
        if path.endswith("/reprovision"):
            return {"status": "provisioning", "detail": "Provisioning queued"}
        if path.endswith("/repair-token"):
            return {
                "accepted": True,
                "message": "Gateway token repaired from the runtime configuration and verified for future requests.",
            }
        raise AssertionError(f"Unexpected proxy call: {method} {path}")

    monkeypatch.setattr(eva_admin_api_client, "request", fake_request)
    client = _build_client()

    checks_response = client.post(f"/infrastructure/openclaw/employees/{employee_id}/run-checks")
    assert checks_response.status_code == 200, checks_response.text
    assert checks_response.json()["accepted"] is True

    reprovision_response = client.post(
        f"/infrastructure/openclaw/employees/{employee_id}/reprovision",
        json={"force": True},
    )
    assert reprovision_response.status_code == 200, reprovision_response.text
    assert reprovision_response.json()["accepted"] is True

    repair_response = client.post(f"/infrastructure/openclaw/employees/{employee_id}/repair-token")
    assert repair_response.status_code == 200, repair_response.text
    assert repair_response.json()["accepted"] is True

    assert calls[0][0] == "POST"
    assert calls[0][1] == f"/openclaw/admin/runtime/employees/{employee_id}/run-checks"
    assert calls[1][1] == f"/openclaw/admin/runtime/employees/{employee_id}/reprovision"
    assert calls[2][1] == f"/openclaw/admin/runtime/employees/{employee_id}/repair-token"


def test_openclaw_reprovision_campaign_proxy(monkeypatch):
    async def fake_request(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        if method == "POST" and path == "/openclaw/admin/runtime/reprovision/campaigns":
            assert kwargs["json"] == {"force": True}
            return {
                "accepted": True,
                "campaign_id": "campaign-123",
                "queued_count": 2,
                "message": "Full-fleet reprovision queued for all current OpenClaw employees.",
            }
        if method == "GET" and path == "/openclaw/admin/runtime/reprovision/campaigns/campaign-123":
            return {
                "campaign_id": "campaign-123",
                "state": "queued",
                "checked_at": "2026-03-26T00:05:00Z",
                "total_employees": 2,
                "queued_count": 2,
                "provisioning_count": 2,
                "ready_count": 0,
                "error_count": 0,
                "employee_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            }
        raise AssertionError(f"Unexpected proxy call: {method} {path}")

    monkeypatch.setattr(eva_admin_api_client, "request", fake_request)
    client = _build_client()

    trigger_response = client.post("/infrastructure/openclaw/reprovision-campaigns", json={"force": True})
    assert trigger_response.status_code == 200, trigger_response.text
    assert trigger_response.json()["campaign_id"] == "campaign-123"

    status_response = client.get("/infrastructure/openclaw/reprovision-campaigns/campaign-123")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["provisioning_count"] == 2
