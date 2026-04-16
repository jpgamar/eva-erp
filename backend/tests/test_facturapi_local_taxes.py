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
