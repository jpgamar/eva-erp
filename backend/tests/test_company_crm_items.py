"""Schema/route tests for the Empresas CRM consolidation.

Pure unit tests — no DB. Validates:
  - Item create/update schemas (kind/contact_method literals, blank-title
    rejection, calendar window validation logic).
  - `/empresas/calendar` is registered BEFORE the dynamic `/{empresa_id}`
    route so it doesn't get swallowed.
  - `/eva-platform/accounts/list-for-link` is registered BEFORE
    `/eva-platform/accounts/{account_id}` (P1 review finding).
  - Public list response shape exposes `pending_count`, `pending_items`,
    `next_action`, `overdue_count`.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from pydantic import ValidationError

from src.empresas.router import _validate_item_window
from src.empresas.schemas import (
    EmpresaCalendarItemResponse,
    EmpresaItemCreate,
    EmpresaItemUpdate,
    EmpresaListPendingItem,
    EmpresaListResponse,
)
from src.main import app


def _all_paths_in_order() -> list[tuple[str, frozenset[str]]]:
    out: list[tuple[str, frozenset[str]]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path:
            out.append((path, frozenset(methods)))
    return out


def _index_of(paths: list[tuple[str, frozenset[str]]], path: str, method: str) -> int:
    for i, (p, methods) in enumerate(paths):
        if p == path and method in methods:
            return i
    return -1


# ── Schema: kind + contact_method literals ──────────────────────────


def test_item_create_accepts_known_kind() -> None:
    data = EmpresaItemCreate(title="Llamar Juan", kind="event", start_at=_dt.datetime.now(_dt.timezone.utc))
    assert data.kind == "event"


def test_item_create_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        EmpresaItemCreate(title="x", kind="bogus")  # type: ignore[arg-type]


def test_item_create_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        EmpresaItemCreate(title="   ")


def test_item_create_strips_title_whitespace() -> None:
    data = EmpresaItemCreate(title="  Recordatorio  ")
    assert data.title == "Recordatorio"


def test_item_update_blank_title_rejected() -> None:
    with pytest.raises(ValidationError):
        EmpresaItemUpdate(title="   ")


def test_item_update_omits_title_means_no_change() -> None:
    data = EmpresaItemUpdate(done=True)
    assert "title" not in data.model_dump(exclude_unset=True)


# ── Helper: window validation ───────────────────────────────────────


def test_validate_item_window_event_requires_date() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _validate_item_window({"kind": "event"})
    assert exc.value.status_code == 400


def test_validate_item_window_end_before_start_rejected() -> None:
    from fastapi import HTTPException

    start = _dt.datetime(2026, 5, 4, 10, 0, tzinfo=_dt.timezone.utc)
    end = _dt.datetime(2026, 5, 4, 9, 0, tzinfo=_dt.timezone.utc)
    with pytest.raises(HTTPException) as exc:
        _validate_item_window({"kind": "event", "start_at": start, "end_at": end})
    assert exc.value.status_code == 400


def test_validate_item_window_todo_no_date_ok() -> None:
    _validate_item_window({"kind": "todo"})


# ── Route ordering ──────────────────────────────────────────────────


def test_calendar_route_registered_before_dynamic_empresa_route() -> None:
    paths = _all_paths_in_order()
    calendar_idx = _index_of(paths, "/api/v1/empresas/calendar", "GET")
    dynamic_idx = _index_of(paths, "/api/v1/empresas/{empresa_id}", "GET")
    assert calendar_idx >= 0, "GET /empresas/calendar must be registered"
    assert dynamic_idx >= 0, "GET /empresas/{empresa_id} must be registered"
    assert calendar_idx < dynamic_idx, (
        f"calendar route at {calendar_idx} must come before dynamic empresa route at {dynamic_idx}"
    )


def test_eva_platform_list_for_link_registered_before_account_dynamic() -> None:
    """P1 review finding: list-for-link was being swallowed by /accounts/{id}."""
    paths = _all_paths_in_order()
    static_idx = _index_of(paths, "/api/v1/eva-platform/accounts/list-for-link", "GET")
    dynamic_idx = _index_of(paths, "/api/v1/eva-platform/accounts/{account_id}", "GET")
    assert static_idx >= 0, "channel_health.list_for_link must be registered"
    assert dynamic_idx >= 0, "accounts.get_account must be registered"
    assert static_idx < dynamic_idx, (
        f"list-for-link at {static_idx} must come before /accounts/{{account_id}} at {dynamic_idx}"
    )


# ── Response shapes ─────────────────────────────────────────────────


def test_empresa_list_response_exposes_pending_metadata() -> None:
    fields = set(EmpresaListResponse.model_fields)
    for required in ("pending_count", "pending_items", "next_action", "overdue_count"):
        assert required in fields, f"EmpresaListResponse missing {required}"


def test_pending_item_includes_kind_and_dates() -> None:
    item = EmpresaListPendingItem(
        id="00000000-0000-0000-0000-000000000001",
        title="Visita",
        kind="event",
        start_at=_dt.datetime.now(_dt.timezone.utc),
    )
    payload = item.model_dump()
    assert payload["kind"] == "event"
    assert payload["start_at"] is not None


def test_list_empresas_response_includes_all_card_contract_fields() -> None:
    """Lock the GET /empresas payload shape so future changes can't
    silently drop fields the frontend card / kanban depend on. The
    review-round-5 finding caught a missing `lifecycle_stage` /
    `version` etc that would have left badges blank and broken the
    optimistic-lock header on stage moves.
    """
    import inspect
    from src.empresas import router as empresas_router

    src = inspect.getsource(empresas_router.list_empresas)
    REQUIRED_KEYS = (
        '"id"',
        '"name"',
        '"status"',
        '"lifecycle_stage"',
        '"ball_on"',
        '"summary_note"',
        '"monthly_amount"',
        '"billing_interval"',
        '"payment_day"',
        '"last_paid_date"',
        '"expected_close_date"',
        '"cancellation_scheduled_at"',
        '"eva_account_id"',
        '"auto_match_attempted"',
        '"grandfathered"',
        '"version"',
        '"subscription_status"',
        '"current_period_end"',
        '"item_count"',
        '"pending_count"',
        '"pending_items"',
        '"next_action"',
        '"overdue_count"',
        '"health"',
    )
    for key in REQUIRED_KEYS:
        assert key in src, f"GET /empresas payload missing key: {key}"


def test_calendar_item_response_supports_all_sources() -> None:
    fields = set(EmpresaCalendarItemResponse.model_fields)
    assert "source" in fields
    # Just check the literal accepts known sources via instantiation.
    for source in ("item", "meeting", "interaction"):
        EmpresaCalendarItemResponse(
            id="00000000-0000-0000-0000-000000000002",
            empresa_id="00000000-0000-0000-0000-000000000003",
            empresa_name="Test",
            source=source,  # type: ignore[arg-type]
            kind="event",
            title="Evento",
        )
