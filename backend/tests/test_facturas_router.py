import asyncio
import inspect
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.facturas.models import Factura
from src.facturas.router import create_factura, download_pdf, download_xml, stamp_factura
from src.facturas.router import get_current_user
from src.facturas.router import get_db
from src.facturas.router import router as facturas_router
from src.facturas.router import facturapi
from src.facturas.schemas import FacturaCreate, FacturaLineItem, FacturaResponse


def _get_delete_factura_route() -> APIRoute:
    for route in facturas_router.routes:
        if isinstance(route, APIRoute) and route.path == "/facturas/{factura_id}" and "DELETE" in route.methods:
            return route
    raise AssertionError("DELETE /facturas/{factura_id} route not found")


def test_delete_factura_route_declares_response_model():
    route = _get_delete_factura_route()
    assert route.response_model is FacturaResponse


def test_stamp_factura_does_not_have_local_facturalineitem_import():
    source = inspect.getsource(stamp_factura)
    assert "from src.facturas.schemas import FacturaLineItem" not in source


class _FakeResult:
    def __init__(self, factura: Factura | None):
        self._factura = factura

    def scalar_one_or_none(self) -> Factura | None:
        return self._factura


class _FakeDB:
    def __init__(self, factura: Factura):
        self.factura = factura
        self.deleted = False

    async def execute(self, _query):
        return _FakeResult(self.factura)

    async def delete(self, _obj):
        self.deleted = True

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    def add(self, _obj):
        return None


def _build_factura(status: str) -> Factura:
    now = datetime.now(timezone.utc)
    return Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_test_123",
        cfdi_uuid="uuid-test-123",
        customer_name="Cliente Demo",
        customer_rfc="XAXX010101000",
        customer_id=None,
        customer_tax_system="601",
        customer_zip="06600",
        use="G03",
        payment_form="28",
        payment_method="PUE",
        line_items_json=[{
            "product_key": "10101504",
            "description": "Servicio demo",
            "quantity": 1,
            "unit_price": 100.0,
            "tax_rate": 0.16,
        }],
        subtotal=Decimal("100.00"),
        tax=Decimal("16.00"),
        isr_retention=Decimal("0.00"),
        iva_retention=Decimal("0.00"),
        total=Decimal("116.00"),
        total_paid=Decimal("0.00"),
        payment_status="unpaid",
        stamp_retry_count=0,
        currency="MXN",
        status=status,
        cancellation_status=None,
        pdf_url="https://example.com/a.pdf",
        xml_url="https://example.com/a.xml",
        notes=None,
        series="A",
        folio_number=1,
        issued_at=now,
        cancelled_at=None,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def _build_test_client(fake_db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(facturas_router)
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    return TestClient(app)


def test_delete_draft_factura_returns_204_without_cancellation_call(monkeypatch):
    cancelled = {"called": False}

    async def _fake_cancel_invoice(*_args, **_kwargs):
        cancelled["called"] = True
        return {"cancellation_status": "accepted"}

    monkeypatch.setattr(facturapi, "cancel_invoice", _fake_cancel_invoice)
    factura = _build_factura(status="draft")
    factura.facturapi_id = None  # local-only draft
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.delete(f"/facturas/{factura.id}")

    assert response.status_code == 204
    assert response.text == ""
    assert fake_db.deleted is True
    assert cancelled["called"] is False


def test_delete_valid_factura_cancels_and_returns_serialized_factura(monkeypatch):
    cancelled = {"called": False}

    async def _fake_cancel_invoice(*_args, **_kwargs):
        cancelled["called"] = True
        return {"cancellation_status": "accepted"}

    monkeypatch.setattr(facturapi, "cancel_invoice", _fake_cancel_invoice)
    factura = _build_factura(status="valid")
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.delete(f"/facturas/{factura.id}")

    assert response.status_code == 200
    assert cancelled["called"] is True
    payload = response.json()
    assert payload["id"] == str(factura.id)
    assert payload["status"] == "cancelled"
    assert payload["cancellation_status"] == "accepted"
    assert payload["cancelled_at"] is not None


# --- Draft mode tests ---


class _CreateFakeDB:
    """Fake DB for POST /facturas tests — captures the Factura passed to .add()."""
    def __init__(self):
        self.added: Factura | None = None

    async def execute(self, _query):
        return _FakeResult(None)

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    def add(self, obj):
        self.added = obj


def _sample_create_payload() -> FacturaCreate:
    return FacturaCreate(
        customer_name="Cliente Demo",
        customer_rfc="XAXX010101000",
        customer_tax_system="601",
        customer_zip="06600",
        line_items=[FacturaLineItem(
            product_key="10101504",
            description="Servicio demo",
            quantity=1,
            unit_price=Decimal("100"),
            tax_rate=Decimal("0.16"),
        )],
    )


def test_create_factura_draft_true_pushes_to_facturapi_and_saves_facturapi_id(monkeypatch):
    create_draft_calls: list[dict] = []

    async def _fake_create_draft(payload):
        create_draft_calls.append(payload)
        return {"id": "fac_draft_abc", "total": 116.0}

    async def _fake_create_invoice(*_a, **_kw):
        raise AssertionError("create_invoice must not be called for draft=true")

    monkeypatch.setattr(facturapi, "create_draft_invoice", _fake_create_draft)
    monkeypatch.setattr(facturapi, "create_invoice", _fake_create_invoice)

    db = _CreateFakeDB()
    user = SimpleNamespace(id=uuid.uuid4())
    asyncio.run(create_factura(_sample_create_payload(), draft=True, db=db, user=user))

    assert len(create_draft_calls) == 1
    assert db.added is not None
    assert db.added.facturapi_id == "fac_draft_abc"
    assert db.added.status == "draft"
    assert db.added.total == Decimal("116.0")


def test_create_factura_draft_true_facturapi_error_does_not_save_local(monkeypatch):
    async def _fake_create_draft(_payload):
        raise HTTPException(status_code=502, detail={"facturapi_error": "bad rfc"})

    monkeypatch.setattr(facturapi, "create_draft_invoice", _fake_create_draft)

    db = _CreateFakeDB()
    user = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_factura(_sample_create_payload(), draft=True, db=db, user=user))
    assert exc_info.value.status_code == 502
    assert db.added is None  # nothing staged for commit


def test_create_factura_draft_false_does_not_call_facturapi(monkeypatch):
    async def _fake_create_draft(*_a, **_kw):
        raise AssertionError("create_draft_invoice must not be called when draft=false")

    async def _fake_create_invoice(*_a, **_kw):
        raise AssertionError("create_invoice must not be called on POST /facturas")

    monkeypatch.setattr(facturapi, "create_draft_invoice", _fake_create_draft)
    monkeypatch.setattr(facturapi, "create_invoice", _fake_create_invoice)

    db = _CreateFakeDB()
    user = SimpleNamespace(id=uuid.uuid4())
    asyncio.run(create_factura(_sample_create_payload(), draft=False, db=db, user=user))

    assert db.added is not None
    assert db.added.facturapi_id is None
    assert db.added.status == "draft"


def test_stamp_factura_enqueues_and_does_not_call_facturapi(monkeypatch):
    """Post-outbox refactor: the stamp endpoint MUST NOT call FacturAPI.

    The whole point of the outbox is that the request handler's only job
    is to durably transition draft → pending_stamp and commit. Any HTTP
    call here would reintroduce the F-4 atomicity bug.
    """

    async def _fake_create_invoice(*_a, **_kw):
        raise AssertionError(
            "create_invoice must not be called from the stamp endpoint — "
            "FacturAPI stamping is the outbox worker's responsibility."
        )

    async def _fake_stamp_draft(*_a, **_kw):
        raise AssertionError(
            "stamp_draft_invoice must not be called from the stamp endpoint — "
            "the outbox worker re-POSTs with idempotency_key instead."
        )

    monkeypatch.setattr(facturapi, "create_invoice", _fake_create_invoice)
    monkeypatch.setattr(facturapi, "stamp_draft_invoice", _fake_stamp_draft)

    factura = _build_factura(status="draft")
    factura.facturapi_id = None
    factura.cfdi_uuid = None
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.post(f"/facturas/{factura.id}/stamp")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending_stamp"
    assert body["cfdi_uuid"] is None


def test_stamp_factura_sets_idempotency_key_to_row_id():
    """The idempotency key is the durable bridge between pending_stamp and
    a successful FacturAPI response — it must be a stable function of the
    factura row (its UUID) so retries send the same key."""

    factura = _build_factura(status="draft")
    factura.facturapi_id = None
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.post(f"/facturas/{factura.id}/stamp")

    assert response.status_code == 202
    # The factura was mutated in place before returning.
    assert factura.status == "pending_stamp"
    assert factura.facturapi_idempotency_key == str(factura.id)
    assert factura.stamp_retry_count == 0
    assert factura.last_stamp_error is None
    assert factura.next_retry_at is None


def test_stamp_factura_clears_existing_facturapi_id():
    """If a draft was previously pushed to Facturapi as a preview draft
    (has facturapi_id but no cfdi_uuid), the outbox must start clean so
    the worker POSTs a fresh invoice with the idempotency key — not try
    to stamp an abandoned FacturAPI draft that our retry logic doesn't
    know about."""

    factura = _build_factura(status="draft")
    factura.facturapi_id = "fac_abandoned_preview_draft"
    factura.cfdi_uuid = None
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.post(f"/facturas/{factura.id}/stamp")

    assert response.status_code == 202
    assert factura.facturapi_id is None
    assert factura.cfdi_uuid is None
    assert factura.status == "pending_stamp"


def test_download_pdf_draft_with_facturapi_id_succeeds(monkeypatch):
    async def _fake_download_pdf(facturapi_id):
        assert facturapi_id == "fac_draft_xyz"
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(facturapi, "download_pdf", _fake_download_pdf)

    factura = _build_factura(status="draft")
    factura.facturapi_id = "fac_draft_xyz"
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.get(f"/facturas/{factura.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_download_pdf_draft_without_facturapi_id_returns_400(monkeypatch):
    async def _fake_download_pdf(_facturapi_id):
        raise AssertionError("must not call Facturapi when no facturapi_id")

    monkeypatch.setattr(facturapi, "download_pdf", _fake_download_pdf)

    factura = _build_factura(status="draft")
    factura.facturapi_id = None
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.get(f"/facturas/{factura.id}/pdf")

    assert response.status_code == 400


def test_delete_draft_with_facturapi_id_cascades_to_facturapi(monkeypatch):
    delete_calls: list[str] = []

    async def _fake_delete_draft(facturapi_id):
        delete_calls.append(facturapi_id)

    monkeypatch.setattr(facturapi, "delete_draft_invoice", _fake_delete_draft)

    factura = _build_factura(status="draft")
    factura.facturapi_id = "fac_draft_to_kill"
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.delete(f"/facturas/{factura.id}")

    assert response.status_code == 204
    assert delete_calls == ["fac_draft_to_kill"]
    assert fake_db.deleted is True


def test_delete_local_only_draft_does_not_call_facturapi(monkeypatch):
    async def _fake_delete_draft(_facturapi_id):
        raise AssertionError("must not call Facturapi for local-only drafts")

    monkeypatch.setattr(facturapi, "delete_draft_invoice", _fake_delete_draft)

    factura = _build_factura(status="draft")
    factura.facturapi_id = None
    fake_db = _FakeDB(factura)
    client = _build_test_client(fake_db)

    response = client.delete(f"/facturas/{factura.id}")

    assert response.status_code == 204
    assert fake_db.deleted is True
