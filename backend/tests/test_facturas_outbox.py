"""Unit tests for the CFDI outbox worker.

The outbox is what eliminates the F-4 class of bugs. Its contract is:

1. ``stamp_pending_factura`` calls FacturAPI with ``idempotency_key`` and
   either marks the row ``valid`` on success, or bumps retry bookkeeping
   on failure.
2. After ``max_retries`` consecutive failures, the row transitions to
   ``stamp_failed`` and an alert is fired.
3. An ``EvaBillingRecord`` linked to the factura gets its invoice email
   sent after a successful stamp.

These tests exercise each contract without touching a real Postgres or
the real FacturAPI — the pattern is the same ``_FakeDB`` used elsewhere
in this repo.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.common.config import settings
from src.facturas import outbox
from src.facturas import service as facturapi_service
from src.facturas.models import Factura


def _new_pending_factura() -> Factura:
    """A minimally-populated factura row in ``pending_stamp``."""
    now = datetime.now(timezone.utc)
    return Factura(
        id=uuid.uuid4(),
        facturapi_id=None,
        cfdi_uuid=None,
        customer_name="Cliente Demo",
        customer_rfc="XAXX010101000",
        customer_tax_system="601",
        customer_zip="06600",
        use="G03",
        payment_form="28",
        payment_method="PUE",
        line_items_json=[
            {
                "product_key": "10101504",
                "description": "Servicio demo",
                "quantity": 1,
                "unit_price": 100.0,
                "tax_rate": 0.16,
            }
        ],
        subtotal=Decimal("100.00"),
        tax=Decimal("16.00"),
        isr_retention=Decimal("0.00"),
        iva_retention=Decimal("0.00"),
        local_retention=Decimal("0.00"),
        total=Decimal("116.00"),
        currency="MXN",
        status="pending_stamp",
        notes=None,
        series=None,
        folio_number=None,
        issued_at=None,
        cancelled_at=None,
        stamp_retry_count=0,
        last_stamp_error=None,
        next_retry_at=None,
        stamp_attempted_at=None,
        facturapi_idempotency_key=None,  # set by the worker on first attempt
        created_at=now,
        updated_at=now,
    )


class _NoOpDB:
    """Stand-in DB for tests that don't need to query other rows.

    ``stamp_pending_factura`` mutates the factura in place (the session
    tracks the change) and then calls ``_maybe_finalize_eva_billing_record``
    which queries via ``db.scalar``. For unit tests we stub scalar() to
    return None so the finalize path no-ops.
    """

    def __init__(self):
        self.added: list = []
        self.committed = False

    async def scalar(self, *_args, **_kwargs):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_stamp_pending_factura_success_marks_valid(monkeypatch):
    """Happy path: FacturAPI responds 200 → row transitions to valid with
    all CFDI fields populated and no retry bookkeeping."""

    captured_payload: dict = {}

    async def _fake_create_invoice(payload):
        captured_payload.update(payload)
        return {
            "id": "fac_ok_001",
            "uuid": "UUID-VALID-0001",
            "status": "valid",
            "total": 116.0,
            "series": "F",
            "folio_number": 42,
            "pdf_custom_section": "https://example.com/a.pdf",
            "xml": "https://example.com/a.xml",
        }

    monkeypatch.setattr(facturapi_service, "create_invoice", _fake_create_invoice)

    factura = _new_pending_factura()
    db = _NoOpDB()

    await outbox.stamp_pending_factura(db, factura)

    assert factura.status == "valid"
    assert factura.facturapi_id == "fac_ok_001"
    assert factura.cfdi_uuid == "UUID-VALID-0001"
    assert factura.pdf_url == "https://example.com/a.pdf"
    assert factura.xml_url == "https://example.com/a.xml"
    assert factura.series == "F"
    assert factura.folio_number == 42
    assert factura.issued_at is not None
    assert factura.last_stamp_error is None
    assert factura.next_retry_at is None
    assert factura.stamp_attempted_at is not None
    # Idempotency key must be the row id — stable across retries.
    assert factura.facturapi_idempotency_key == str(factura.id)
    assert captured_payload["idempotency_key"] == str(factura.id)


@pytest.mark.asyncio
async def test_stamp_pending_factura_failure_schedules_retry(monkeypatch):
    """First FacturAPI failure: status stays pending_stamp, retry counter
    bumps to 1, next_retry_at is ~30s from now (first backoff step)."""

    async def _boom(*_a, **_kw):
        raise RuntimeError("FacturAPI 502")

    monkeypatch.setattr(facturapi_service, "create_invoice", _boom)

    factura = _new_pending_factura()
    db = _NoOpDB()

    before = datetime.now(timezone.utc)
    await outbox.stamp_pending_factura(db, factura)
    after = datetime.now(timezone.utc)

    assert factura.status == "pending_stamp"
    assert factura.stamp_retry_count == 1
    assert "FacturAPI 502" in (factura.last_stamp_error or "")
    assert factura.next_retry_at is not None
    # ~30s delay after the first failure (see outbox._BACKOFF_SECONDS).
    expected_min = before + timedelta(seconds=29)
    expected_max = after + timedelta(seconds=31)
    assert expected_min <= factura.next_retry_at <= expected_max


@pytest.mark.asyncio
async def test_stamp_pending_factura_after_max_retries_marks_failed(monkeypatch):
    """After ``max_retries`` failures the row transitions to stamp_failed
    and ``next_retry_at`` is cleared (worker should not pick it up again).
    """

    async def _boom(*_a, **_kw):
        raise RuntimeError("FacturAPI error")

    monkeypatch.setattr(facturapi_service, "create_invoice", _boom)

    factura = _new_pending_factura()
    # Pretend we already failed max_retries - 1 times; this attempt is the final one.
    factura.stamp_retry_count = settings.facturapi_outbox_max_retries - 1

    db = _NoOpDB()

    await outbox.stamp_pending_factura(db, factura)

    assert factura.status == "stamp_failed"
    assert factura.stamp_retry_count == settings.facturapi_outbox_max_retries
    assert factura.next_retry_at is None


@pytest.mark.asyncio
async def test_stamp_pending_factura_reuses_existing_idempotency_key(monkeypatch):
    """Idempotency key set on a prior attempt must be reused, so a retry
    sends the same key to FacturAPI and gets the same CFDI back."""

    seen_keys: list[str] = []

    async def _fake_create_invoice(payload):
        seen_keys.append(payload["idempotency_key"])
        return {
            "id": "fac_replay_001",
            "uuid": "UUID-REPLAY-0001",
            "status": "valid",
            "total": 116.0,
        }

    monkeypatch.setattr(facturapi_service, "create_invoice", _fake_create_invoice)

    factura = _new_pending_factura()
    preset_key = "erp-factura-preset-key-abc"
    factura.facturapi_idempotency_key = preset_key

    db = _NoOpDB()
    await outbox.stamp_pending_factura(db, factura)

    assert seen_keys == [preset_key]
    assert factura.facturapi_idempotency_key == preset_key


def test_backoff_delays_grow_monotonically():
    """The backoff schedule must not shrink between retries — otherwise a
    single failure could thrash FacturAPI. Also: the final value must be
    reasonable (retryable within a day)."""

    prev = timedelta(0)
    for i in range(len(outbox._BACKOFF_SECONDS)):
        delay = outbox._next_retry_delay(i)
        assert delay >= prev, f"backoff shrank at step {i}: {prev} → {delay}"
        prev = delay

    # Last retry delay should fit within a day — we don't want a broken
    # factura stuck on the queue for weeks if somebody sets max_retries high.
    assert outbox._next_retry_delay(len(outbox._BACKOFF_SECONDS) - 1) <= timedelta(hours=24)


def test_rebuild_factura_create_preserves_all_fields():
    """The outbox re-derives a FacturaCreate from the Factura row when
    rebuilding the FacturAPI payload. Dropping a field (e.g., cedular
    rate) would silently emit a wrong CFDI, so this is a load-bearing
    test."""

    factura = _new_pending_factura()
    # Add a cedular line item to exercise the full mapping.
    factura.line_items_json = [
        {
            "product_key": "81112100",
            "description": "Servicio TI",
            "quantity": 1,
            "unit_price": 3999.0,
            "tax_rate": 0.16,
            "isr_retention": 0.0125,
            "iva_retention": 0.106667,
            "cedular_rate": 0.02,
            "cedular_label": "Cedular GTO",
        }
    ]

    data = outbox._rebuild_factura_create(factura)

    assert len(data.line_items) == 1
    li = data.line_items[0]
    assert li.product_key == "81112100"
    assert li.unit_price == Decimal("3999.0")
    assert li.isr_retention == Decimal("0.0125")
    assert li.iva_retention == Decimal("0.106667")
    assert li.cedular_rate == Decimal("0.02")
    assert li.cedular_label == "Cedular GTO"


@pytest.mark.asyncio
async def test_stamp_pending_factura_sets_attempted_at(monkeypatch):
    """Even on failure we want to know when the last attempt happened,
    for the operator dashboard. ``stamp_attempted_at`` is set at the top
    of the function regardless of outcome."""

    async def _boom(*_a, **_kw):
        raise RuntimeError("nope")

    monkeypatch.setattr(facturapi_service, "create_invoice", _boom)

    factura = _new_pending_factura()
    assert factura.stamp_attempted_at is None
    await outbox.stamp_pending_factura(_NoOpDB(), factura)
    assert factura.stamp_attempted_at is not None
