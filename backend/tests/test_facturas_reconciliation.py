"""Unit tests for the FacturAPI → ERP reconciliation loop.

The reconciliation loop serves two distinct jobs: adoption of CFDIs
stamped outside the ERP, and healing of local rows that drifted from
FacturAPI's truth. Each branch has a test here so a future refactor
can't silently break one without the other turning red.

Notable fixture: the F-4 simulation. On 2026-04-18 we lost factura
F-4 (SERVIACERO COMERCIAL, $4,162.29, 2026-03-23, UUID
0B7DD523-8189-4131-A584-BEB731A54CA3). The adoption test replays
FacturAPI's response for exactly that folio and asserts the ERP
inserts a matching row — so this bug can never silently regress.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.facturas import reconciliation
from src.facturas.models import Factura


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ReconDB:
    """DB stand-in that answers by facturapi_id lookup.

    Reconciliation calls ``db.scalar(select(Factura).where(facturapi_id == id))``
    per invoice. We map facturapi_id → Factura here to let tests seed the
    ERP's current state.
    """

    def __init__(self, seed: list[Factura] | None = None):
        self.rows: dict[str, Factura] = {}
        for factura in (seed or []):
            if factura.facturapi_id:
                self.rows[factura.facturapi_id] = factura
        self.added: list[Factura] = []
        self.committed = False

    async def scalar(self, stmt):
        # SQLAlchemy Select exposes compare_value via _where_criteria; for
        # tests, we cheat and read the bound parameter directly from the
        # compiled statement. Simpler: rely on the fact that reconciliation
        # builds exactly one where clause ``Factura.facturapi_id == X``.
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)
        # Parse out the literal facturapi_id in the WHERE clause.
        # Cheaper than wiring a real Postgres for unit tests.
        import re

        m = re.search(r"facturapi_id\s*=\s*'([^']+)'", sql)
        if not m:
            return None
        return self.rows.get(m.group(1))

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Factura) and obj.facturapi_id:
            self.rows[obj.facturapi_id] = obj

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        return None


def _f4_fixture() -> dict:
    """The FacturAPI payload for F-4 as captured from the live API on
    2026-04-18 (truncated to the fields reconciliation consumes)."""
    return {
        "id": "69c0ed31bbe7908eb8bc9a24",
        "uuid": "0B7DD523-8189-4131-A584-BEB731A54CA3",
        "type": "I",
        "status": "valid",
        "date": "2026-03-23T07:35:13.950Z",
        "series": "F",
        "folio_number": 4,
        "payment_form": "04",
        "payment_method": "PUE",
        "currency": "MXN",
        "total": 4162.29,
        "customer": {
            "legal_name": "SERVIACERO COMERCIAL",
            "tax_id": "SCO8007138GA",
            "tax_system": "601",
            "address": {"zip": "38010"},
        },
        "items": [
            {
                "quantity": 1,
                "product": {
                    "description": "Suscripcion EvaAI Standard Mensual",
                    "product_key": "81112100",
                    "price": 3999.0,
                    "taxes": [
                        {"type": "IVA", "rate": 0.16},
                        {"type": "ISR", "rate": 0.0125, "withholding": True},
                        {"type": "IVA", "rate": 0.106667, "withholding": True},
                    ],
                },
            }
        ],
        "use": "G03",
    }


@pytest.mark.asyncio
async def test_reconciliation_adopts_f4():
    """Regression for the 2026-04-18 F-4 incident. After a reconciliation
    pass, the missing factura must exist in the ERP DB with the right
    totals.
    """
    db = _ReconDB(seed=[])
    stats = {
        "fetched": 0, "adopted": 0, "healed": 0, "cancelled_synced": 0,
        "matched": 0, "skipped": 0, "failed": 0,
    }

    await reconciliation._adopt_or_heal(db, _f4_fixture(), stats)

    assert stats["adopted"] == 1
    assert len(db.added) == 1
    adopted = db.added[0]
    assert adopted.facturapi_id == "69c0ed31bbe7908eb8bc9a24"
    assert adopted.cfdi_uuid == "0B7DD523-8189-4131-A584-BEB731A54CA3"
    assert adopted.folio_number == 4
    assert adopted.customer_name == "SERVIACERO COMERCIAL"
    assert adopted.customer_rfc == "SCO8007138GA"
    assert adopted.subtotal == Decimal("3999.00")
    assert adopted.total == Decimal("4162.29")
    assert adopted.status == "valid"
    assert adopted.series == "F"


@pytest.mark.asyncio
async def test_reconciliation_heals_pending_stamp_row():
    """If the outbox stamped a factura at FacturAPI but then crashed
    before committing the response, the local row is ``pending_stamp``
    while FacturAPI shows valid. Reconciliation must promote the row.
    """
    # Seed: factura exists locally but still marked pending_stamp.
    # (facturapi_id set because the outbox did write it before the crash,
    # OR not set — reconciliation matches on facturapi_id only when present;
    # the heal path matches the same row.)
    factura = Factura(
        id=uuid.uuid4(),
        facturapi_id="69c0ed31bbe7908eb8bc9a24",
        cfdi_uuid=None,
        customer_name="SERVIACERO COMERCIAL",
        customer_rfc="SCO8007138GA",
        use="G03",
        payment_form="04",
        payment_method="PUE",
        subtotal=Decimal("3999.00"),
        tax=Decimal("639.84"),
        isr_retention=Decimal("49.99"),
        iva_retention=Decimal("426.57"),
        local_retention=Decimal("0.00"),
        total=Decimal("4162.29"),
        currency="MXN",
        status="pending_stamp",
        stamp_retry_count=2,
        last_stamp_error="connection reset",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = _ReconDB(seed=[factura])
    stats = {
        "fetched": 0, "adopted": 0, "healed": 0, "cancelled_synced": 0,
        "matched": 0, "skipped": 0, "failed": 0,
    }

    await reconciliation._adopt_or_heal(db, _f4_fixture(), stats)

    assert stats["healed"] == 1
    assert stats["adopted"] == 0
    # The seed row was mutated in place; no new row inserted.
    assert factura.status == "valid"
    assert factura.cfdi_uuid == "0B7DD523-8189-4131-A584-BEB731A54CA3"
    assert factura.folio_number == 4
    assert factura.last_stamp_error is None
    assert factura.next_retry_at is None


@pytest.mark.asyncio
async def test_reconciliation_syncs_cancellation():
    """If someone cancels a CFDI from the FacturAPI dashboard, the next
    reconciliation must mark the local row cancelled too.
    """
    factura = Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_cancel_me",
        cfdi_uuid="UUID-CANCEL-0001",
        customer_name="Cliente Demo",
        customer_rfc="XAXX010101000",
        use="G03",
        payment_form="28",
        payment_method="PUE",
        subtotal=Decimal("100.00"),
        tax=Decimal("16.00"),
        isr_retention=Decimal("0.00"),
        iva_retention=Decimal("0.00"),
        local_retention=Decimal("0.00"),
        total=Decimal("116.00"),
        currency="MXN",
        status="valid",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = _ReconDB(seed=[factura])
    stats = {
        "fetched": 0, "adopted": 0, "healed": 0, "cancelled_synced": 0,
        "matched": 0, "skipped": 0, "failed": 0,
    }

    cancelled_payload = {
        **_f4_fixture(),
        "id": "fac_cancel_me",
        "uuid": "UUID-CANCEL-0001",
        "status": "canceled",  # FacturAPI spelling
        "folio_number": 99,
    }

    await reconciliation._adopt_or_heal(db, cancelled_payload, stats)

    assert stats["cancelled_synced"] == 1
    assert factura.status == "cancelled"  # normalized ERP spelling
    assert factura.cancelled_at is not None


@pytest.mark.asyncio
async def test_reconciliation_matched_row_is_no_op():
    """If the local row is already valid and FacturAPI agrees, nothing
    should change — just count as matched."""
    factura = Factura(
        id=uuid.uuid4(),
        facturapi_id="fac_already_synced",
        cfdi_uuid="UUID-SYNCED-0001",
        customer_name="Cliente Demo",
        customer_rfc="XAXX010101000",
        use="G03",
        payment_form="28",
        payment_method="PUE",
        subtotal=Decimal("100.00"),
        tax=Decimal("16.00"),
        isr_retention=Decimal("0.00"),
        iva_retention=Decimal("0.00"),
        local_retention=Decimal("0.00"),
        total=Decimal("116.00"),
        currency="MXN",
        status="valid",
        folio_number=10,
        series="F",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    original_status = factura.status
    db = _ReconDB(seed=[factura])
    stats = {
        "fetched": 0, "adopted": 0, "healed": 0, "cancelled_synced": 0,
        "matched": 0, "skipped": 0, "failed": 0,
    }

    payload = {
        **_f4_fixture(),
        "id": "fac_already_synced",
        "uuid": "UUID-SYNCED-0001",
        "status": "valid",
        "folio_number": 10,
    }

    await reconciliation._adopt_or_heal(db, payload, stats)

    assert stats["matched"] == 1
    assert factura.status == original_status
    assert len(db.added) == 0


@pytest.mark.asyncio
async def test_reconciliation_once_paginates(monkeypatch):
    """End-to-end through reconcile_facturapi_once: paginates, stops at
    total_pages, aggregates stats."""

    # Two pages, 2 invoices per page.
    pages = {
        1: {
            "page": 1,
            "total_pages": 2,
            "data": [
                {**_f4_fixture(), "id": "a_001", "uuid": "UUID-A-1", "folio_number": 1},
                {**_f4_fixture(), "id": "a_002", "uuid": "UUID-A-2", "folio_number": 2},
            ],
        },
        2: {
            "page": 2,
            "total_pages": 2,
            "data": [
                {**_f4_fixture(), "id": "b_001", "uuid": "UUID-B-1", "folio_number": 3},
                {**_f4_fixture(), "id": "b_002", "uuid": "UUID-B-2", "folio_number": 4},
            ],
        },
    }

    async def _fake_fetch(page: int) -> dict:
        return pages[page]

    monkeypatch.setattr(reconciliation, "_fetch_facturapi_page", _fake_fetch)

    db = _ReconDB(seed=[])
    stats = await reconciliation.reconcile_facturapi_once(db)

    assert stats["fetched"] == 4
    assert stats["adopted"] == 4
    assert len(db.added) == 4
    assert {f.folio_number for f in db.added} == {1, 2, 3, 4}


def test_extract_facturapi_fields_parses_taxes():
    """The field extraction must correctly split IVA trasladado, ISR
    retención, and IVA retención — getting this wrong would corrupt
    every adopted row's retention totals.
    """
    fields = reconciliation._extract_facturapi_fields(_f4_fixture())

    assert fields["subtotal"] == Decimal("3999.00")
    # IVA 16% on $3,999 = $639.84
    assert fields["tax"] == Decimal("639.84")
    # ISR retention 1.25% on $3,999 = $49.99 (rounded)
    assert fields["isr_retention"] == Decimal("49.99")
    # IVA retention 10.6667% on $3,999 = $426.56 (banker's rounding).
    # The true F-4 CFDI uses this same rounding — confirmed by:
    # 3999 + 639.84 - 49.99 - 426.56 = 4162.29 (matches FacturAPI total).
    assert fields["iva_retention"] == Decimal("426.56")
    assert fields["local_retention"] == Decimal("0.00")
    # total from the FacturAPI response (we trust their math over ours)
    assert fields["total"] == Decimal("4162.29")
