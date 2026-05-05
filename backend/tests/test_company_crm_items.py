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


def test_items_list_route_registered_before_dynamic_empresa_route() -> None:
    """`GET /empresas/items` MUST come before `GET /empresas/{empresa_id}`
    so the dynamic UUID route doesn't swallow the literal `items` segment.
    Same convention we applied to /calendar in the original CRM
    consolidation (P1 from that earlier review).
    """
    paths = _all_paths_in_order()
    items_idx = _index_of(paths, "/api/v1/empresas/items", "GET")
    dynamic_idx = _index_of(paths, "/api/v1/empresas/{empresa_id}", "GET")
    assert items_idx >= 0, "GET /empresas/items must be registered"
    assert dynamic_idx >= 0
    assert items_idx < dynamic_idx, (
        f"items route at {items_idx} must come before dynamic empresa route at {dynamic_idx}"
    )


def test_post_items_route_registered() -> None:
    """`POST /empresas/items` (top-level, internal-task-friendly) must
    exist alongside the existing `POST /empresas/{empresa_id}/items`."""
    paths = _all_paths_in_order()
    top_level = _index_of(paths, "/api/v1/empresas/items", "POST")
    nested = _index_of(paths, "/api/v1/empresas/{empresa_id}/items", "POST")
    assert top_level >= 0
    assert nested >= 0
    assert top_level < nested, (
        "Top-level /items POST must register before /{empresa_id}/items POST"
    )


def test_bulk_stage_route_registered() -> None:
    paths = _all_paths_in_order()
    assert _index_of(paths, "/api/v1/empresas/bulk-stage", "POST") >= 0


def test_bulk_stage_409_on_version_mismatch() -> None:
    """Atomic: if even one empresa has a stale `version`, the whole
    batch rejects with 409 BulkStageConflict and NO empresa moves."""
    import asyncio
    import uuid as _uuid
    from types import SimpleNamespace

    import pytest as _pytest
    from fastapi import HTTPException
    from src.empresas.router import bulk_stage_empresas
    from src.empresas.schemas import BulkStageMove, BulkStageRequest

    e1_id = _uuid.uuid4()
    e2_id = _uuid.uuid4()

    class _StubEmpresa:
        def __init__(self, id_, version, lifecycle="prospecto", subscription_status=None):
            self.id = id_
            self.version = version
            self.lifecycle_stage = lifecycle
            self.subscription_status = subscription_status
            self.eva_account_id = None
            self.expected_close_date = None
            self.grandfathered = False

    e1 = _StubEmpresa(e1_id, version=2, lifecycle="prospecto")
    e2 = _StubEmpresa(e2_id, version=5, lifecycle="prospecto")

    class _ScalarsAll:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _ScalarsAll(self._items)

    class _Db:
        async def execute(self, _q):
            return _Result([e1, e2])

        def add(self, _obj):
            pass

        async def flush(self):
            pass

    payload = BulkStageRequest(
        moves=[
            BulkStageMove(empresa_id=e1_id, version=2),
            # Stale version for e2 → whole batch must reject.
            BulkStageMove(empresa_id=e2_id, version=99),
        ],
        lifecycle_stage_to="interesado",  # type: ignore[arg-type]
    )

    with _pytest.raises(HTTPException) as exc:
        asyncio.run(
            bulk_stage_empresas(
                payload,
                db=_Db(),  # type: ignore[arg-type]
                eva_db=None,
                user=SimpleNamespace(id=_uuid.uuid4()),  # type: ignore[arg-type]
            )
        )
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert detail["reason"] == "BulkStageConflict"
    conflict_reasons = {c["reason"] for c in detail["conflicts"]}
    assert "OptimisticLockMismatch" in conflict_reasons
    # Atomic — neither empresa was mutated.
    assert e1.lifecycle_stage == "prospecto"
    assert e2.lifecycle_stage == "prospecto"


def test_bulk_stage_409_on_inactivo_with_active_subscription() -> None:
    """Bulk move to `inactivo` rejects empresas with active/trialing
    subscriptions — operator must drag those individually so the
    cancel-subscription dialog runs."""
    import asyncio
    import uuid as _uuid
    from types import SimpleNamespace

    import pytest as _pytest
    from fastapi import HTTPException
    from src.empresas.router import bulk_stage_empresas
    from src.empresas.schemas import BulkStageMove, BulkStageRequest

    e_id = _uuid.uuid4()

    class _StubEmpresa:
        def __init__(self):
            self.id = e_id
            self.version = 1
            self.lifecycle_stage = "operativo"
            self.subscription_status = "active"
            self.eva_account_id = _uuid.uuid4()
            self.expected_close_date = None
            self.grandfathered = False

    e = _StubEmpresa()

    class _ScalarsAll:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _ScalarsAll(self._items)

    class _Db:
        async def execute(self, _q):
            return _Result([e])

        def add(self, _obj):
            pass

        async def flush(self):
            pass

    payload = BulkStageRequest(
        moves=[BulkStageMove(empresa_id=e_id, version=1)],
        lifecycle_stage_to="inactivo",  # type: ignore[arg-type]
    )

    with _pytest.raises(HTTPException) as exc:
        asyncio.run(
            bulk_stage_empresas(
                payload,
                db=_Db(),  # type: ignore[arg-type]
                eva_db=None,
                user=SimpleNamespace(id=_uuid.uuid4()),  # type: ignore[arg-type]
            )
        )
    assert exc.value.status_code == 409
    reasons = {c["reason"] for c in exc.value.detail["conflicts"]}
    assert "BulkInactivoNeedsCancel" in reasons
    assert e.lifecycle_stage == "operativo"  # untouched


def test_list_items_kind_filter_parses_csv() -> None:
    """`?kind=todo,event` should produce an IN-list filter."""
    import asyncio
    import uuid as _uuid
    from types import SimpleNamespace

    from src.empresas.router import list_items_across_empresas

    captured: list[Any] = []

    class _Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class _Db:
        async def execute(self, q):
            captured.append(str(q))
            return _Result([])

    asyncio.run(
        list_items_across_empresas(
            assigned_to=None,
            done=False,
            overdue=False,
            kind="todo,event",
            empresa_id=None,
            limit=50,
            db=_Db(),  # type: ignore[arg-type]
            user=SimpleNamespace(id=_uuid.uuid4()),  # type: ignore[arg-type]
        )
    )
    assert captured, "execute() must have been called"
    rendered = captured[0]
    # SQLAlchemy renders the IN clause with the filter values.
    assert "kind IN" in rendered or "kind in" in rendered.lower()


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


def test_list_empresas_returns_post_auto_match_cache_and_version() -> None:
    """Round-7 finding: after lazy auto-match runs inside list_empresas,
    the response payload must reflect the bumped version and synced
    billing cache from the freshly-mutated ORM row, not the pre-match
    snapshot. Otherwise the next save 409s on optimistic-lock and the
    card renders linked-but-stale.
    """
    import asyncio
    import datetime as _dt
    import uuid as _uuid
    from types import SimpleNamespace
    from src.empresas import router as empresas_router

    empresa_id = _uuid.uuid4()

    class _Row:
        def __init__(self) -> None:
            self.id = empresa_id
            self.name = "Acme"
            self.logo_url = None
            self.status = "prospecto"
            self.lifecycle_stage = "demo"
            self.ball_on = None
            self.summary_note = None
            self.monthly_amount = None
            self.billing_interval = "monthly"
            self.payment_day = None
            self.last_paid_date = None
            self.expected_close_date = None
            self.cancellation_scheduled_at = None
            self.eva_account_id = None
            self.auto_match_attempted = False
            self.grandfathered = False
            self.version = 0
            self.subscription_status = None
            self.current_period_end = None
            self.person_type = None
            self.rfc = None
            self.item_count = 0
            self.pending_count = 0

    refreshed = empresas_router.Empresa(
        id=empresa_id,
        name="Acme",
        version=7,
        eva_account_id=_uuid.uuid4(),
        auto_match_attempted=True,
        billing_interval="annual",
        subscription_status="active",
        current_period_end=_dt.datetime(2026, 12, 1, tzinfo=_dt.timezone.utc),
    )

    # Patch the helpers list_empresas calls so we can drive only the
    # serialization path without standing up a real DB.
    async def _fake_compute_health(eva_db, _id_map):
        return {empresa_id: {
            "status": "healthy",
            "unhealthy_count": 0,
            "linked_account_name": "Linked",
            "messenger": {"present": False, "healthy": False, "count": 0},
            "instagram": {"present": False, "healthy": False, "count": 0},
            "whatsapp": {"present": False, "healthy": False, "count": 0},
        }}

    async def _fake_attempt_auto_match(_db, _eva_db, emp):
        # Mimic the production helper: stamp attempted + sync from the
        # refreshed snapshot we built above.
        emp.eva_account_id = refreshed.eva_account_id
        emp.auto_match_attempted = True
        emp.version = refreshed.version
        emp.billing_interval = refreshed.billing_interval
        emp.subscription_status = refreshed.subscription_status
        emp.current_period_end = refreshed.current_period_end

    rows = [_Row()]

    class _ScalarsAll:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _Result:
        def __init__(self, kind: str):
            self.kind = kind

        def all(self):
            if self.kind == "rows":
                return rows
            if self.kind == "items":
                return []
            return []

        def scalars(self):
            if self.kind == "load":
                return _ScalarsAll([refreshed])
            return _ScalarsAll([])

    sequence = ["rows", "items", "load"]

    class _FakeDb:
        def __init__(self):
            self._idx = 0

        async def execute(self, _q):
            kind = sequence[self._idx]
            self._idx += 1
            return _Result(kind)

        async def flush(self):
            return None

    fake_db = _FakeDb()
    monkeypatch_targets = {
        "_compute_health_for_empresas": _fake_compute_health,
        "_attempt_auto_match": _fake_attempt_auto_match,
    }
    originals: dict[str, Any] = {}
    for name, replacement in monkeypatch_targets.items():
        originals[name] = getattr(empresas_router, name)
        setattr(empresas_router, name, replacement)

    try:
        result = asyncio.run(
            empresas_router.list_empresas(
                search=None,
                db=fake_db,  # type: ignore[arg-type]
                user=SimpleNamespace(id=_uuid.uuid4()),  # type: ignore[arg-type]
                eva_db=fake_db,  # type: ignore[arg-type]
            )
        )
    finally:
        for name, original in originals.items():
            setattr(empresas_router, name, original)

    assert len(result) == 1
    payload = result[0]
    assert payload["version"] == 7, "version must reflect post-match bump"
    assert payload["billing_interval"] == "annual"
    assert payload["subscription_status"] == "active"
    assert payload["current_period_end"] == "2026-12-01T00:00:00+00:00"
    assert payload["eva_account_id"] is not None
    assert payload["auto_match_attempted"] is True


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


def test_empresa_calendar_unions_items_meetings_and_interactions() -> None:
    """Round-8 P3: prove `empresa_calendar()` actually merges all three
    sources. Drives the route handler with a fake DB that returns mock
    item / meeting / interaction rows and checks the merged payload.
    """
    import asyncio
    import datetime as _dt
    import uuid as _uuid
    from types import SimpleNamespace
    from src.empresas import router as empresas_router

    empresa_id = _uuid.uuid4()
    now = _dt.datetime(2026, 5, 10, 12, 0, tzinfo=_dt.timezone.utc)

    item_id = _uuid.uuid4()
    meeting_id = _uuid.uuid4()
    interaction_id = _uuid.uuid4()

    item_row = SimpleNamespace(
        id=item_id,
        empresa_id=empresa_id,
        title="Visita Acme",
        description="Discutir propuesta",
        kind="event",
        contact_method="visit",
        start_at=now,
        end_at=now + _dt.timedelta(hours=1),
        due_at=None,
        reminder_at=None,
        completed_at=None,
        assigned_to=None,
    )
    meeting_row = SimpleNamespace(
        id=meeting_id,
        empresa_id=empresa_id,
        empresa_name="Acme",
        title="Reunión legacy",
        date=now - _dt.timedelta(days=2),
        duration_minutes=30,
        notes_markdown="Quedamos en mandar contrato",
    )
    interaction = SimpleNamespace(
        id=interaction_id,
        empresa_id=empresa_id,
        type="whatsapp",
        summary="Saludo inicial",
        date=(now - _dt.timedelta(days=1)).date(),
    )

    class _ItemRows:
        def all(self):
            return [(item_row, "Acme")]

    class _MeetingRows:
        def all(self):
            return [meeting_row]

    class _InteractionRows:
        def all(self):
            return [(interaction, "Acme")]

    sequence = ["items", "meetings", "interactions"]

    class _FakeDb:
        def __init__(self):
            self._idx = 0

        async def execute(self, _q, *_args, **_kwargs):
            kind = sequence[self._idx]
            self._idx += 1
            if kind == "items":
                return _ItemRows()
            if kind == "meetings":
                return _MeetingRows()
            return _InteractionRows()

    payload = asyncio.run(
        empresas_router.empresa_calendar(
            range_from=now - _dt.timedelta(days=30),
            range_to=now + _dt.timedelta(days=30),
            empresa_id=empresa_id,
            db=_FakeDb(),  # type: ignore[arg-type]
            user=SimpleNamespace(id=_uuid.uuid4()),  # type: ignore[arg-type]
        )
    )
    sources = sorted({entry.source for entry in payload})
    assert sources == ["interaction", "item", "meeting"], (
        f"calendar must blend all three sources; got {sources}"
    )
    by_source = {entry.source: entry for entry in payload}
    assert by_source["item"].title == "Visita Acme"
    assert by_source["meeting"].title == "Reunión legacy"
    assert by_source["meeting"].end_at == meeting_row.date + _dt.timedelta(minutes=30)
    assert by_source["interaction"].contact_method == "whatsapp"


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
