from __future__ import annotations

from src.dashboard.router import DashboardResponse
from src.main import app


def test_removed_sections_are_not_mounted():
    paths = {route.path for route in app.routes}

    assert not any(path.startswith("/api/v1/vault") for path in paths)
    assert not any(path.startswith("/api/v1/okrs") for path in paths)
    assert not any(path.startswith("/api/v1/assistant") for path in paths)


def test_dashboard_contract_no_longer_exposes_vault_metrics():
    fields = set(DashboardResponse.model_fields)

    assert "vault_combined_usd" not in fields
    assert "vault_service_count" not in fields
    assert "vault_by_category" not in fields
