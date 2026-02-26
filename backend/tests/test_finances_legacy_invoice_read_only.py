import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.finances.router import get_current_user
from src.finances.router import get_db
from src.finances.router import router as finances_router


class _FakeDB:
    async def execute(self, _query):
        raise AssertionError("DB should not be touched for legacy invoice mutating routes")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(finances_router)
    app.dependency_overrides[get_db] = lambda: _FakeDB()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4(), role="admin")
    return TestClient(app)


def test_create_invoice_route_is_gone() -> None:
    client = _build_client()
    response = client.post(
        "/finances/invoices",
        json={
            "customer_name": "Demo",
            "line_items": [{"description": "Service", "quantity": 1, "unit_price": "100.00", "total": "100.00"}],
            "issue_date": "2026-02-26",
            "due_date": "2026-03-05",
        },
    )
    assert response.status_code == 410


def test_update_invoice_route_is_gone() -> None:
    client = _build_client()
    response = client.patch(f"/finances/invoices/{uuid.uuid4()}", json={"status": "paid"})
    assert response.status_code == 410


def test_delete_invoice_route_is_gone() -> None:
    client = _build_client()
    response = client.delete(f"/finances/invoices/{uuid.uuid4()}")
    assert response.status_code == 410
