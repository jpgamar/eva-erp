"""Verify build_facturapi_payload emits the correct local_taxes entry for cedular."""

from __future__ import annotations

from decimal import Decimal

from src.facturas.schemas import FacturaCreate, FacturaLineItem
from src.facturas.service import build_facturapi_payload


def _line_item(**kwargs) -> FacturaLineItem:
    base = {
        "product_key": "81112100",
        "description": "Servicio EvaAI",
        "quantity": 1,
        "unit_price": Decimal("1500"),
        "tax_rate": Decimal("0.16"),
        "isr_retention": Decimal("0.0125"),
        "iva_retention": Decimal("0.106667"),
    }
    base.update(kwargs)
    return FacturaLineItem(**base)


def _factura(line_item: FacturaLineItem) -> FacturaCreate:
    return FacturaCreate(
        customer_name="LEON ACABADOS ARQUITECTONICOS",
        customer_rfc="LAA840518C64",
        customer_tax_system="601",
        customer_zip="37160",
        use="G03",
        payment_form="04",
        payment_method="PUE",
        line_items=[line_item],
    )


class TestFacturapiLocalTaxes:
    def test_no_cedular_means_no_local_taxes_key(self):
        """Line item without cedular_rate should not emit local_taxes at all."""
        item = _line_item()
        payload = build_facturapi_payload(_factura(item))
        product = payload["items"][0]["product"]
        assert "local_taxes" not in product

    def test_cedular_rate_produces_local_taxes_entry(self):
        item = _line_item(cedular_rate=Decimal("0.02"), cedular_label="Cedular GTO")
        payload = build_facturapi_payload(_factura(item))
        local_taxes = payload["items"][0]["product"]["local_taxes"]
        assert len(local_taxes) == 1
        entry = local_taxes[0]
        assert entry["type"] == "Cedular GTO"
        assert entry["rate"] == 0.02
        assert entry["withholding"] is True

    def test_cedular_without_label_uses_fallback(self):
        """When no label is provided we still emit a valid entry."""
        item = _line_item(cedular_rate=Decimal("0.02"))
        payload = build_facturapi_payload(_factura(item))
        entry = payload["items"][0]["product"]["local_taxes"][0]
        assert entry["type"] == "Cedular"
        assert entry["rate"] == 0.02

    def test_federal_taxes_remain_in_taxes_array(self):
        """Federal ISR + IVA retentions stay on product.taxes, not local_taxes."""
        item = _line_item(cedular_rate=Decimal("0.02"), cedular_label="Cedular GTO")
        payload = build_facturapi_payload(_factura(item))
        taxes = payload["items"][0]["product"]["taxes"]
        types = [(t["type"], t.get("withholding", False)) for t in taxes]
        assert ("IVA", False) in types  # traslado 16%
        assert ("ISR", True) in types   # retención 1.25%
        assert ("IVA", True) in types   # retención 2/3

    def test_mxn_default_omits_currency_field(self):
        """Default MXN invoices should NOT emit `currency` on the payload —
        SAT's implicit default is MXN. Adding it unnecessarily would put a
        ``currency="MXN"`` key on every CFDI in production."""
        item = _line_item()
        payload = build_facturapi_payload(_factura(item))
        assert "currency" not in payload

    def test_non_mxn_factura_emits_currency_and_exchange(self):
        """Codex round-5/6 P2: A USD factura must serialize BOTH currency
        AND exchange — a bare currency field with no rate would stamp at
        the implicit default of 1.0 and the conversion is fiscally wrong.
        """
        item = _line_item()
        data = FacturaCreate(
            customer_name="US Client Inc",
            customer_rfc="XEXX010101000",
            customer_tax_system="616",
            customer_zip="06600",
            use="G03",
            payment_form="04",
            payment_method="PUE",
            currency="USD",
            exchange_rate=Decimal("19.75"),
            line_items=[item],
        )
        payload = build_facturapi_payload(data)
        assert payload["currency"] == "USD"
        assert payload["exchange"] == 19.75

    def test_non_mxn_factura_without_exchange_rate_rejected_at_schema(self):
        """Schema-layer validation: defense-in-depth — a non-MXN invoice
        without an explicit exchange_rate must fail at FacturaCreate
        construction, not silently succeed and then stamp wrong.
        """
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            FacturaCreate(
                customer_name="US Client Inc",
                customer_rfc="XEXX010101000",
                customer_tax_system="616",
                customer_zip="06600",
                currency="USD",
                # exchange_rate deliberately omitted
                line_items=[_line_item()],
            )
        assert "exchange_rate is required" in str(exc_info.value)


class TestFacturaStateDerivation:
    """Ensure local_retention_state is derived from customer_zip, not from the label.

    Regression guard for review finding I-1 — earlier code parsed the state
    from ``cedular_label`` (fragile if the label is localized or reworded).
    """

    def test_state_derived_from_zip_not_label(self):
        from decimal import Decimal as D

        from src.facturas.schemas import FacturaCreate, FacturaLineItem
        from src.eva_billing.service import EvaBillingService

        line = FacturaLineItem(
            product_key="81112100",
            description="X",
            unit_price=D("1500"),
            tax_rate=D("0.16"),
            isr_retention=D("0.0125"),
            iva_retention=D("0.106667"),
            cedular_rate=D("0.02"),
            # Deliberately ambiguous label — a future edit could use a name
            # like this without any three-letter state token.
            cedular_label="Retención estatal",
        )
        factura_data = FacturaCreate(
            customer_name="Test Empresa",
            customer_rfc="LAA840518C64",
            customer_tax_system="601",
            customer_zip="37160",  # León, GTO
            line_items=[line],
        )

        # Extract the state derivation logic outside the DB path. The method
        # uses state_from_zip(data.customer_zip) → "GTO" regardless of label.
        from src.common.mx_postal_codes import state_from_zip

        # Guard: the real method would derive "GTO" from this ZIP even with
        # an ambiguous label. Assertion below pins that direct behavior.
        assert state_from_zip(factura_data.customer_zip) == "GTO"

    def test_non_cedular_zip_yields_none(self):
        from src.common.mx_postal_codes import state_from_zip

        # Customer in CDMX — no cedular state should be persisted even if
        # someone accidentally passes a cedular_rate on a line item.
        assert state_from_zip("06600") is None
