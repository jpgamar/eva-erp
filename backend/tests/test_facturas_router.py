import inspect
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.facturas.models import Factura
from src.facturas.router import get_current_user
from src.facturas.router import get_db
from src.facturas.router import router as facturas_router
from src.facturas.router import stamp_factura
from src.facturas.router import facturapi
from src.facturas.schemas import FacturaResponse


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
