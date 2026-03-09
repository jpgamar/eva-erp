import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.eva_billing.models import EvaBillingRecord
from src.eva_billing.service import EvaBillingService


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self._row = row
        self.added = []

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._row)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None


def test_resend_invoice_email_marks_record_sent(monkeypatch):
    account_id = uuid.uuid4()
    factura_id = uuid.uuid4()
    record = EvaBillingRecord(
        account_id=account_id,
        source_type="subscription_invoice",
        idempotency_key="billing-record-1",
        factura_id=factura_id,
        recipient_email="owner@example.com",
        status="issued",
        currency="MXN",
    )
    factura = SimpleNamespace(
        id=factura_id,
        cfdi_uuid="UUID-123",
        customer_name="Cliente SA de CV",
        customer_rfc="ABC123456T89",
        customer_tax_system="601",
        customer_zip="11560",
        use="G03",
        total=Decimal("123.45"),
        pdf_url="https://files.example.com/invoice.pdf",
        xml_url="https://files.example.com/invoice.xml",
    )
    fake_db = _FakeSession((record, factura))
    service = EvaBillingService()

    async def _fake_send_invoice_email(**_kwargs):
        return "sent", None

    monkeypatch.setattr(service, "_send_invoice_email", _fake_send_invoice_email)

    result = asyncio.run(
        service.resend_invoice_email(fake_db, account_id=account_id, cfdi_uuid="UUID-123")
    )

    assert result.email_status == "sent"
    assert record.status == "email_sent"
    assert isinstance(record.email_sent_at, datetime)
    assert record.email_sent_at.tzinfo == timezone.utc
