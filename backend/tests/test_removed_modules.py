"""Verify removed product surfaces (vault/okrs/assistant/meetings/documents)
no longer mount their routers and that the dashboard contract no longer
exposes the metrics that were tied to them.

The legacy tables remain (no destructive drop scheduled), so we only
assert the API surface — visiting `/api/v1/vault`, `/api/v1/okrs`, etc.
must return 404 and the dashboard contract must omit `vault_*` /
`meeting_*` fields.
"""
from __future__ import annotations

from src.dashboard.router import DashboardResponse
from src.main import app


REMOVED_PREFIXES = (
    "/api/v1/vault",
    "/api/v1/okrs",
    "/api/v1/assistant",
    "/api/v1/meetings",
    "/api/v1/documents",
    # empresas-ux-pass: tasks/boards rolled into empresa_items
    "/api/v1/tasks",
    "/api/v1/boards",
)


def _all_paths() -> list[str]:
    return [getattr(route, "path", "") for route in app.routes]


def test_removed_router_prefixes_are_not_mounted() -> None:
    paths = _all_paths()
    for prefix in REMOVED_PREFIXES:
        offenders = [p for p in paths if p.startswith(prefix)]
        assert not offenders, f"removed prefix {prefix!r} still has routes: {offenders}"


def test_dashboard_response_omits_removed_metrics() -> None:
    fields = set(DashboardResponse.model_fields)
    forbidden = {
        "vault_combined_usd",
        "vault_service_count",
        "vault_by_category",
        "total_meetings",
        "upcoming_meetings",
        "meetings_this_month",
    }
    assert not (fields & forbidden), (
        f"dashboard contract still exposes removed metrics: {fields & forbidden}"
    )


def test_customers_router_still_mounted_for_facturas() -> None:
    """The Facturas helper still calls /api/v1/customers — keep it mounted."""
    paths = _all_paths()
    assert any(p.startswith("/api/v1/customers") for p in paths), (
        "/api/v1/customers must remain mounted: Facturas-side helper depends on it"
    )
