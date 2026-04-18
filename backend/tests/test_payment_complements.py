"""Tests for Complementos de Pago (CFDI tipo P).

The complement workflow is a multi-stage thing: register payment →
outbox picks up → builds tipo P payload → POSTs to FacturAPI → marks
valid. Each stage has a test here.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.common.config import settings
from src.facturas import outbox
from src.facturas import payment_complements
from src.facturas import service as facturapi_service
from src.facturas.models import CfdiPayment, Factura
from src.facturas.schemas import CfdiPaymentCreate


def _make_ppd_factura(*, total: str = "10000.00", paid: str = "0.00") -> Factura:
    """A valid PPD factura eligible for complements."""
    return Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_ppd_001",
        cfdi_uuid="UUID-PPD-0001",
        customer_name="Cliente PPD",
        customer_rfc="CPP200101XXX",
        customer_tax_system="601",
        customer_zip="06600",
        use="G03",
        payment_form="99",  # Por definir — PPD often uses 99
        payment_method="PPD",
        line_items_json=[
            {
                "product_key": "81112100",
                "description": "Consultoría",
                "quantity": 1,
                "unit_price": 8620.69,
                "tax_rate": 0.16,
            }
        ],
        subtotal=Decimal("8620.69"),
        tax=Decimal("1379.31"),
        isr_retention=Decimal("0.00"),
        iva_retention=Decimal("0.00"),
        local_retention=Decimal("0.00"),
        total=Decimal(total),
        currency="MXN",
        status="valid",
        total_paid=Decimal(paid),
        payment_status="unpaid" if paid == "0.00" else "partial",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_derive_payment_status_buckets():
    """unpaid / partial / paid math with 1-cent tolerance."""
    assert payment_complements._derive_payment_status(Decimal("100.00"), Decimal("0.00")) == "unpaid"
    assert payment_complements._derive_payment_status(Decimal("100.00"), Decimal("50.00")) == "partial"
    assert payment_complements._derive_payment_status(Decimal("100.00"), Decimal("99.99")) == "paid"
    # Exactly full
    assert payment_complements._derive_payment_status(Decimal("100.00"), Decimal("100.00")) == "paid"
    # Float-noise overage (shouldn't happen but shouldn't crash)
    assert payment_complements._derive_payment_status(Decimal("100.00"), Decimal("100.01")) == "paid"


def test_days_until_sat_deadline_regular_case():
    """Payment 2026-03-23 → deadline 2026-04-05. On 2026-04-01 that's 4 days left."""
    payment = date(2026, 3, 23)
    today = date(2026, 4, 1)
    assert payment_complements.days_until_sat_deadline(payment, today=today) == 4


def test_days_until_sat_deadline_overdue():
    """Same payment, 2 days past deadline."""
    payment = date(2026, 3, 23)
    today = date(2026, 4, 7)
    assert payment_complements.days_until_sat_deadline(payment, today=today) == -2


def test_days_until_sat_deadline_december_rolls_to_january():
    """December payment → January 5 next year deadline."""
    payment = date(2025, 12, 28)
    today = date(2026, 1, 3)
    assert payment_complements.days_until_sat_deadline(payment, today=today) == 2


def test_build_payment_complement_payload_shape():
    """The tipo P body must have type=P, customer, and a single complements
    entry with type='pago' pointing back to the original UUID."""
    factura = _make_ppd_factura()
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        currency="MXN",
        payment_amount=Decimal("5800.00"),
        last_balance=Decimal("10000.00"),
        installment=1,
        status="pending_stamp",
    )

    payload = facturapi_service.build_payment_complement_payload(
        factura=factura,
        payment=payment,
        idempotency_key="pago:test-001",
    )

    assert payload["type"] == "P"
    assert payload["idempotency_key"] == "pago:test-001"
    assert payload["customer"]["tax_id"] == factura.customer_rfc
    assert payload["customer"]["address"]["zip"] == factura.customer_zip
    # Critical: no top-level items on a CFDI de Pagos (items are replaced
    # by the complement payload).
    assert "items" not in payload
    # Complement structure
    assert len(payload["complements"]) == 1
    comp = payload["complements"][0]
    assert comp["type"] == "pago"
    assert len(comp["data"]) == 1
    pago = comp["data"][0]
    assert pago["payment_form"] == "28"
    assert len(pago["related_documents"]) == 1
    rel = pago["related_documents"][0]
    assert rel["uuid"] == factura.cfdi_uuid
    assert rel["amount"] == 5800.00
    assert rel["installment"] == 1
    assert rel["last_balance"] == 10000.00
    # Proportional rebuild: factura.subtotal=8620.69, factura.total=10000.
    # proportion=5800/10000=0.58 → base=8620.69*0.58=5000.00, IVA 16%.
    assert rel["taxes"][0]["type"] == "IVA"
    assert rel["taxes"][0]["rate"] == 0.16
    assert rel["taxes"][0]["base"] == 5000.00


def test_build_payment_complement_payload_preserves_retentions():
    """Regression for the P1 math bug (Codex review, 2026-04-18): PPD
    invoices with federal retentions (persona-moral client like F-4)
    cannot use the naive ``base = payment_amount / (1 + tax_rate)``
    formula, because cash received = subtotal + IVA − retenciones.
    The correct base is a proportional slice of the original
    factura.subtotal.

    For the F-4-shaped scenario ($3,999 subtotal + 16% IVA − 1.25% ISR −
    10.6667% IVA retention = $4,162.29 cash), a full payment of
    4162.29 must produce base=3999.00 (not the naive 3588.18).
    """
    factura = Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_f4_like",
        cfdi_uuid="UUID-F4-LIKE",
        customer_name="Cliente PM",
        customer_rfc="CPM200101XXX",
        customer_tax_system="601",
        customer_zip="06600",
        use="G03",
        payment_form="99",
        payment_method="PPD",
        line_items_json=[],
        subtotal=Decimal("3999.00"),
        tax=Decimal("639.84"),
        isr_retention=Decimal("49.99"),
        iva_retention=Decimal("426.56"),
        local_retention=Decimal("0.00"),
        total=Decimal("4162.29"),
        currency="MXN",
        status="valid",
        total_paid=Decimal("0"),
        payment_status="unpaid",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        currency="MXN",
        payment_amount=Decimal("4162.29"),  # full payment
        last_balance=Decimal("4162.29"),
        installment=1,
        status="pending_stamp",
    )

    payload = facturapi_service.build_payment_complement_payload(
        factura=factura,
        payment=payment,
        idempotency_key="pago:test-retentions",
    )

    rel = payload["complements"][0]["data"][0]["related_documents"][0]
    # Base must recover the original subtotal on a full payment.
    assert rel["taxes"][0]["base"] == 3999.00
    assert rel["taxes"][0]["rate"] == 0.16

    # Retentions on the complement must mirror the factura's (both as
    # withholding=True entries with their SAT-registered rates).
    withholdings = [t for t in rel["taxes"] if t.get("withholding")]
    isr = next(t for t in withholdings if t["type"] == "ISR")
    iva_ret = next(t for t in withholdings if t["type"] == "IVA")
    assert isr["base"] == 3999.00
    assert abs(isr["rate"] - 0.0125) < 1e-6
    assert iva_ret["base"] == 3999.00
    assert abs(iva_ret["rate"] - 0.106667) < 1e-4


class _NoOpDB:
    def __init__(self, factura: Factura | None = None):
        self._factura = factura
        self.added: list = []

    async def get(self, _cls, _id):
        return self._factura

    async def scalar(self, *_a, **_k):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_register_payment_rejects_non_ppd():
    """Only PPD facturas can have complements. PUE is closed at emission."""
    factura = _make_ppd_factura()
    factura.payment_method = "PUE"
    db = _NoOpDB(factura)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        await payment_complements.register_payment(
            db=db,
            factura_id=factura.id,
            data=CfdiPaymentCreate(
                payment_date=date(2026, 4, 15),
                payment_form="28",
                payment_amount=Decimal("100.00"),
            ),
        )
    assert excinfo.value.status_code == 400
    assert "PPD" in excinfo.value.detail


@pytest.mark.asyncio
async def test_register_payment_rejects_excess():
    """Payment can't exceed outstanding balance."""
    factura = _make_ppd_factura(total="1000.00", paid="800.00")  # 200 outstanding
    db = _NoOpDB(factura)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        await payment_complements.register_payment(
            db=db,
            factura_id=factura.id,
            data=CfdiPaymentCreate(
                payment_date=date(2026, 4, 15),
                payment_form="28",
                payment_amount=Decimal("500.00"),
            ),
        )
    assert excinfo.value.status_code == 400
    assert "exceeds outstanding balance" in excinfo.value.detail


@pytest.mark.asyncio
async def test_register_payment_bumps_totals():
    """Happy path: creates payment row, bumps factura totals and status."""
    factura = _make_ppd_factura(total="1000.00", paid="0.00")
    db = _NoOpDB(factura)

    payment = await payment_complements.register_payment(
        db=db,
        factura_id=factura.id,
        data=CfdiPaymentCreate(
            payment_date=date(2026, 4, 15),
            payment_form="28",
            payment_amount=Decimal("400.00"),
        ),
    )

    assert payment.status == "pending_stamp"
    assert payment.payment_amount == Decimal("400.00")
    assert payment.facturapi_idempotency_key == f"pago:{payment.id}"
    assert factura.total_paid == Decimal("400.00")
    assert factura.payment_status == "partial"


@pytest.mark.asyncio
async def test_register_payment_marks_paid_when_balance_zero():
    factura = _make_ppd_factura(total="1000.00", paid="400.00")
    db = _NoOpDB(factura)

    await payment_complements.register_payment(
        db=db,
        factura_id=factura.id,
        data=CfdiPaymentCreate(
            payment_date=date(2026, 4, 16),
            payment_form="28",
            payment_amount=Decimal("600.00"),
        ),
    )
    assert factura.total_paid == Decimal("1000.00")
    assert factura.payment_status == "paid"


class _OutboxDB:
    """DB stand-in for outbox.stamp_pending_payment tests."""

    def __init__(self, factura: Factura | None = None):
        self._factura = factura

    async def get(self, _cls, _id):
        return self._factura

    async def scalar(self, *_a, **_k):
        return None

    def add(self, _obj):
        return None

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_stamp_pending_payment_success(monkeypatch):
    """Outbox calls FacturAPI with a tipo P payload and marks valid."""
    factura = _make_ppd_factura()
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        currency="MXN",
        payment_amount=Decimal("1000.00"),
        installment=1,
        status="pending_stamp",
    )

    captured: dict = {}

    async def _fake_create_invoice(payload):
        captured.update(payload)
        return {
            "id": "fac_p_001",
            "uuid": "UUID-P-0001",
            "status": "valid",
            "total": 1000.0,
        }

    monkeypatch.setattr(facturapi_service, "create_invoice", _fake_create_invoice)

    db = _OutboxDB(factura=factura)
    await outbox.stamp_pending_payment(db, payment)

    assert payment.status == "valid"
    assert payment.facturapi_id == "fac_p_001"
    assert payment.cfdi_uuid == "UUID-P-0001"
    assert captured["type"] == "P"
    assert captured["idempotency_key"] == f"pago:{payment.id}"


def test_build_payment_complement_payload_emits_cedular():
    """Codex round-2 P2: PPD invoices with a state cedular retention
    (e.g., GTO 2%) must carry that retention on the tipo-P complement
    too, under ``local_taxes``. Otherwise the complement's tax profile
    is short and SAT rejects it or the client's IVA acreditable drifts.
    """
    factura = Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_cedular_ppd",
        cfdi_uuid="UUID-CEDULAR-PPD",
        customer_name="Cliente GTO",
        customer_rfc="CGT200101XXX",
        customer_tax_system="601",
        customer_zip="37160",  # GTO zip
        use="G03",
        payment_form="99",
        payment_method="PPD",
        line_items_json=[],
        subtotal=Decimal("3999.00"),
        tax=Decimal("639.84"),
        isr_retention=Decimal("49.99"),
        iva_retention=Decimal("426.56"),
        local_retention=Decimal("79.98"),  # 2% of 3999
        local_retention_state="GTO",
        local_retention_rate=Decimal("0.02"),
        total=Decimal("4082.31"),
        currency="MXN",
        status="valid",
        total_paid=Decimal("0"),
        payment_status="unpaid",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        currency="MXN",
        payment_amount=Decimal("4082.31"),
        installment=1,
        status="pending_stamp",
    )

    payload = facturapi_service.build_payment_complement_payload(
        factura=factura,
        payment=payment,
        idempotency_key="pago:test-cedular",
    )

    rel = payload["complements"][0]["data"][0]["related_documents"][0]
    assert "local_taxes" in rel, (
        "Complement for a cedular-state PPD must carry local_taxes; "
        "missing this leaves SAT's tax profile short and breaks the "
        "client's IVA acreditable."
    )
    local = rel["local_taxes"][0]
    assert local["type"] == "GTO"
    assert local["withholding"] is True
    assert abs(local["rate"] - 0.02) < 1e-6
    assert local["base"] == 3999.00


@pytest.mark.asyncio
async def test_stamp_pending_payment_without_original_uuid_fails_fast():
    """A complement can't reference an unstamped PPD — mark failed, don't retry.

    This is a permanent failure (the data isn't retrievable), so we skip
    the backoff entirely.
    """
    factura = _make_ppd_factura()
    factura.cfdi_uuid = None  # not yet stamped
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        payment_amount=Decimal("100.00"),
        installment=1,
        status="pending_stamp",
    )
    db = _OutboxDB(factura=factura)

    await outbox.stamp_pending_payment(db, payment)

    assert payment.status == "stamp_failed"
    assert "unstamped" in (payment.last_stamp_error or "")


@pytest.mark.asyncio
async def test_stamp_failed_rolls_back_factura_total_paid(monkeypatch):
    """Codex round-2 P1 regression: when a payment transitions to
    stamp_failed after retries, the parent factura's total_paid +
    payment_status must be unwound — otherwise subsequent registrations
    get false "exceeds outstanding balance" errors.
    """
    from fastapi import HTTPException

    async def _permanent_fail(*_a, **_kw):
        # Permanent error classification triggers immediate stamp_failed.
        raise HTTPException(
            status_code=502,
            detail={"facturapi_error": {"message": "tax_id is invalid"}},
        )

    monkeypatch.setattr(facturapi_service, "create_invoice", _permanent_fail)

    factura = _make_ppd_factura(total="10000.00", paid="0.00")
    # Simulate what register_payment() already bumped before stamping.
    factura.total_paid = Decimal("500.00")
    factura.payment_status = "partial"

    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        currency="MXN",
        payment_amount=Decimal("500.00"),
        installment=1,
        status="pending_stamp",
    )

    db = _OutboxDB(factura=factura)
    await outbox.stamp_pending_payment(db, payment)

    assert payment.status == "stamp_failed"
    # Rollback: total_paid should be back to 0 and status back to unpaid.
    assert factura.total_paid == Decimal("0.00")
    assert factura.payment_status == "unpaid"


@pytest.mark.asyncio
async def test_stamp_pending_payment_retry_on_network_error(monkeypatch):
    """Transient FacturAPI error → backoff + stays pending_stamp."""
    async def _boom(*_a, **_kw):
        raise RuntimeError("Facturapi 502")

    monkeypatch.setattr(facturapi_service, "create_invoice", _boom)

    factura = _make_ppd_factura()
    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=date(2026, 4, 15),
        payment_form="28",
        payment_amount=Decimal("100.00"),
        installment=1,
        status="pending_stamp",
    )
    db = _OutboxDB(factura=factura)

    before = datetime.now(timezone.utc)
    await outbox.stamp_pending_payment(db, payment)

    assert payment.status == "pending_stamp"
    assert payment.stamp_retry_count == 1
    assert payment.next_retry_at is not None
    assert payment.next_retry_at > before
    assert payment.next_retry_at <= before + timedelta(seconds=60)
