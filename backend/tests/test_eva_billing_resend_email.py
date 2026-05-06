import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.eva_billing.models import EvaBillingRecord
from src.eva_billing.schemas import EvaBillingCustomer
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
        facturapi_id="facturapi-invoice-123",
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


def test_send_invoice_email_disables_sendgrid_tracking(monkeypatch):
    """Regression guard: invoice emails must NOT include SendGrid-rewritten links.

    Without an explicit `tracking_settings` block, SendGrid rewrites every
    <a href> to a branded-link redirect (url<n>.goeva.ai/ls/click?upn=...) —
    those subdomains pointed at a decommissioned Hetzner VPS, so customer
    clicks died with ERR_CONNECTION_TIMED_OUT (Acabados report, May 2026).
    Mirror the disabled-tracking pattern from empresas/reminders.py and
    eva_platform/onboarding.py.
    """
    captured: dict = {}

    class _FakeResponse:
        status_code = 202

    class _FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, _url, *, headers=None, json=None):  # noqa: ARG002
            captured["url"] = _url
            captured["json"] = json
            return _FakeResponse()

    # Stub out attachment download + httpx client.
    monkeypatch.setattr(
        "src.eva_billing.service.httpx.AsyncClient", _FakeAsyncClient
    )

    async def _no_attachments(_factura, _uuid_short):
        return []

    service = EvaBillingService()
    monkeypatch.setattr(service, "_download_invoice_attachments", _no_attachments)
    # Provide a non-empty SendGrid API key so the early-return check passes.
    monkeypatch.setattr(
        "src.eva_billing.service.settings.sendgrid_api_key",
        "SG.test-key",
        raising=False,
    )

    factura = SimpleNamespace(
        id=uuid.uuid4(),
        cfdi_uuid="UUID-123",
        pdf_url="https://files.example.com/invoice.pdf",
        xml_url="https://files.example.com/invoice.xml",
    )
    customer = EvaBillingCustomer(
        legal_name="Cliente SA de CV",
        tax_id="ABC123456T89",
        tax_regime="601",
        postal_code="11560",
        cfdi_use="G03",
        person_type="persona_moral",
    )

    status, error = asyncio.run(
        service._send_invoice_email(
            recipient_emails=["customer@example.com"],
            customer=customer,
            factura=factura,
            total=Decimal("123.45"),
        )
    )

    assert status == "sent", error
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"

    body = captured["json"]
    # Tracking must be explicitly disabled. Match the exact dict shape used by
    # empresas/reminders.py:200-214 and eva_platform/onboarding.py:323.
    assert body["mail_settings"]["bypass_list_management"]["enable"] is True
    assert body["tracking_settings"]["click_tracking"]["enable"] is False
    assert body["tracking_settings"]["click_tracking"]["enable_text"] is False
    assert body["tracking_settings"]["open_tracking"]["enable"] is False
    assert body["tracking_settings"]["subscription_tracking"]["enable"] is False
