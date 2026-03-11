from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from src.eva_billing.models import EvaBillingRecord
from src.eva_billing.schemas import (
    EvaBillingRefundRequest,
    EvaBillingStampResponse,
)
from src.eva_billing.service import EvaBillingService, compute_hmac_signature
from src.eva_billing.schemas import EvaBillingChargeQuote, EvaBillingCustomer, EvaBillingQuoteRequest
from src.facturas.models import Factura


class _FakeDB:
    def __init__(self, *, record: EvaBillingRecord, factura: Factura) -> None:
        self.record = record
        self.factura = factura
        self.added: list[object] = []

    async def scalar(self, _query):
        return self.record

    async def get(self, _model, _id):
        if _id == self.factura.id:
            return self.factura
        return None

    def add(self, obj):
        if isinstance(obj, Factura) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self):
        return None


def test_quote_applies_persona_moral_retentions() -> None:
    service = EvaBillingService()
    response = service.quote(
        EvaBillingQuoteRequest(
            account_id="00000000-0000-0000-0000-000000000001",
            owner_email="owner@example.com",
            customer=EvaBillingCustomer(
                legal_name="Cliente Demo SA de CV",
                tax_id="ABC123456T89",
                tax_regime="601",
                postal_code="11560",
                cfdi_use="G03",
                person_type="persona_moral",
            ),
            charge=EvaBillingChargeQuote(
                kind="subscription",
                description="Suscripcion EvaAI Standard",
                base_subtotal_minor=399_900,
                interval="monthly",
                plan_tier="standard",
            ),
        )
    )

    assert response.retention_applicable is True
    assert response.iva_minor == 63_984
    assert response.isr_retention_minor == 4_999
    assert response.iva_retention_minor == 42_656
    assert response.payable_total_minor == 416_229


def test_compute_hmac_signature_is_stable() -> None:
    body = b'{"hello":"world"}'
    signature = compute_hmac_signature("secret", "1700000000", body)

    assert signature == compute_hmac_signature("secret", "1700000000", body)


def test_resolve_recipient_emails_falls_back_to_owner() -> None:
    service = EvaBillingService()

    assert service._resolve_recipient_emails("owner@example.com", []) == ["owner@example.com"]


@pytest.mark.asyncio
async def test_send_invoice_email_uses_billing_sender(monkeypatch) -> None:
    service = EvaBillingService()
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 202

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr("src.eva_billing.service.httpx.AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr("src.eva_billing.service.settings.sendgrid_api_key", "sg-test")
    monkeypatch.setattr("src.eva_billing.service.settings.billing_invoice_from_email", "hi@goeva.ai")
    monkeypatch.setattr("src.eva_billing.service.settings.billing_invoice_from_name", "EvaAI")
    monkeypatch.setattr("src.eva_billing.service.settings.sendgrid_reply_to", "hi@goeva.ai")

    status, error = await service._send_invoice_email(
        recipient_emails=["finance@example.com", "ap@example.com"],
        customer=EvaBillingCustomer(
            legal_name="Cliente Demo SA de CV",
            tax_id="ABC123456T89",
            tax_regime="601",
            postal_code="11560",
            cfdi_use="G03",
            person_type="persona_moral",
        ),
        factura=Factura(
            id=uuid.uuid4(),
            facturapi_id="fac_123",
            cfdi_uuid="uuid-123",
            customer_name="Cliente Demo SA de CV",
            customer_rfc="ABC123456T89",
            customer_id=None,
            account_id=uuid.uuid4(),
            customer_tax_system="601",
            customer_zip="11560",
            use="G03",
            payment_form="04",
            payment_method="PUE",
            line_items_json=[],
            subtotal=Decimal("3999.00"),
            tax=Decimal("639.84"),
            isr_retention=Decimal("49.99"),
            iva_retention=Decimal("426.56"),
            total=Decimal("4162.29"),
            currency="MXN",
            status="valid",
            notes=None,
            pdf_url="https://files.example.com/invoice.pdf",
            xml_url="https://files.example.com/invoice.xml",
            series=None,
            folio_number=None,
            issued_at=None,
            created_by=None,
        ),
        total=Decimal("4162.29"),
    )

    assert status == "sent"
    assert error is None
    payload = captured["json"]
    assert payload["from"]["email"] == "hi@goeva.ai"
    assert payload["from"]["name"] == "EvaAI"
    assert payload["reply_to"]["email"] == "hi@goeva.ai"
    assert payload["personalizations"] == [
        {"to": [{"email": "finance@example.com"}]},
        {"to": [{"email": "ap@example.com"}]},
    ]


@pytest.mark.asyncio
async def test_refund_returns_egreso_metadata_for_partial_refund(monkeypatch) -> None:
    service = EvaBillingService()
    account_id = uuid.uuid4()
    original_factura_id = uuid.uuid4()
    original_factura = Factura(
        id=original_factura_id,
        facturapi_id="fac_original",
        cfdi_uuid="uuid-original",
        customer_name="Cliente Demo SA de CV",
        customer_rfc="ABC123456T89",
        customer_id=None,
        account_id=account_id,
        customer_tax_system="601",
        customer_zip="11560",
        use="G03",
        payment_form="04",
        payment_method="PUE",
        line_items_json=[],
        subtotal=Decimal("3999.00"),
        tax=Decimal("639.84"),
        isr_retention=Decimal("49.99"),
        iva_retention=Decimal("426.56"),
        total=Decimal("4162.29"),
        currency="MXN",
        status="valid",
        notes=None,
        pdf_url="https://files.example.com/original.pdf",
        xml_url="https://files.example.com/original.xml",
        series=None,
        folio_number=None,
        issued_at=None,
        created_by=None,
    )
    record = EvaBillingRecord(
        account_id=account_id,
        source_type="subscription_invoice",
        idempotency_key="evt-refund",
        stripe_invoice_id="in_123",
        stripe_payment_intent_id="pi_123",
        stripe_charge_id="ch_123",
        factura_id=original_factura_id,
        status="issued",
        currency="MXN",
    )
    fake_db = _FakeDB(record=record, factura=original_factura)

    async def _fake_create_egreso_invoice(_payload):
        return {
            "id": "fac_egreso",
            "uuid": "uuid-egreso",
            "status": "valid",
            "pdf_custom_section": "https://files.example.com/egreso.pdf",
            "xml": "https://files.example.com/egreso.xml",
        }

    monkeypatch.setattr("src.facturas.service.create_egreso_invoice", _fake_create_egreso_invoice)

    response = await service.refund(
        fake_db,
        EvaBillingRefundRequest(
            account_id=account_id,
            owner_email="owner@example.com",
            idempotency_key="refund-evt",
            stripe_invoice_id="in_123",
            stripe_payment_intent_id="pi_123",
            stripe_charge_id="ch_123",
            refund_amount_minor=4000,
            original_total_minor=416229,
            currency="MXN",
        ),
    )

    assert isinstance(response, EvaBillingStampResponse)
    assert response.status == "refund_issued"
    assert response.cfdi_uuid == "uuid-egreso"
    assert response.pdf_url == "https://files.example.com/egreso.pdf"
    assert response.xml_url == "https://files.example.com/egreso.xml"
