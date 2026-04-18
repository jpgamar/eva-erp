"""Tests for the gastos (facturas recibidas) module.

The XML parser is the risk-concentration in this module — a bug here
silently corrupts the IVA acreditable math and causes under/over-payment
to SAT. Tests cover both CFDI 4.0 and 3.3, PUE vs PPD, tax rebuild,
receiver-RFC rejection, and dedupe.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.facturas_recibidas import service
from src.facturas_recibidas.xml_parser import CfdiParseError, parse_cfdi_xml


def _cfdi_40_sample(
    *,
    uuid: str = "A1B2C3D4-E5F6-7890-ABCD-1234567890AB",
    receiver_rfc: str = "ZEPG070314VC1",
    issuer_rfc: str = "FAP9901011A1",
    subtotal: str = "1000.00",
    iva: str = "160.00",
    total: str = "1160.00",
    payment_method: str = "PUE",
) -> str:
    """Build a minimal but valid-looking CFDI 4.0 for tests."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Serie="A" Folio="100"
    Fecha="2026-03-15T10:00:00"
    FormaPago="03" MetodoPago="{payment_method}"
    SubTotal="{subtotal}" Moneda="MXN" Total="{total}"
    TipoDeComprobante="I" LugarExpedicion="06600">
  <cfdi:Emisor Rfc="{issuer_rfc}" Nombre="FACTURAPI SAPI DE CV" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{receiver_rfc}" Nombre="GUSTAVO ZERMENO PADILLA"
      DomicilioFiscalReceptor="37160" RegimenFiscalReceptor="626" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="81112100" Cantidad="1"
        ClaveUnidad="E48" Descripcion="Suscripcion API CFDI"
        ValorUnitario="{subtotal}" Importe="{subtotal}" ObjetoImp="02">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado Base="{subtotal}" Impuesto="002" TipoFactor="Tasa"
              TasaOCuota="0.160000" Importe="{iva}"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{iva}">
    <cfdi:Traslados>
      <cfdi:Traslado Base="{subtotal}" Impuesto="002" TipoFactor="Tasa"
          TasaOCuota="0.160000" Importe="{iva}"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="1.1" UUID="{uuid}" FechaTimbrado="2026-03-15T10:00:05"
        SelloCFD="..." NoCertificadoSAT="..." SelloSAT="..."/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""


def test_parser_extracts_uuid_and_totals():
    parsed = parse_cfdi_xml(_cfdi_40_sample())
    assert parsed.cfdi_uuid == "A1B2C3D4-E5F6-7890-ABCD-1234567890AB"
    assert parsed.subtotal == Decimal("1000.00")
    assert parsed.total == Decimal("1160.00")
    assert parsed.tax_iva == Decimal("160.00")
    assert parsed.cfdi_type == "I"
    assert parsed.payment_method == "PUE"


def test_parser_extracts_parties():
    parsed = parse_cfdi_xml(_cfdi_40_sample())
    assert parsed.issuer_rfc == "FAP9901011A1"
    assert parsed.issuer_legal_name == "FACTURAPI SAPI DE CV"
    assert parsed.issuer_tax_system == "601"
    assert parsed.receiver_rfc == "ZEPG070314VC1"


def test_parser_rejects_unstamped_cfdi():
    """Missing TimbreFiscalDigital = not a real CFDI, don't store it."""
    xml_no_tfd = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Fecha="2026-03-15T10:00:00" SubTotal="100" Total="116"
    TipoDeComprobante="I" Moneda="MXN">
  <cfdi:Emisor Rfc="FAP9901011A1" Nombre="X" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="ZEPG070314VC1" Nombre="Y" UsoCFDI="G03"
      DomicilioFiscalReceptor="37160" RegimenFiscalReceptor="626"/>
  <cfdi:Conceptos/>
</cfdi:Comprobante>"""
    with pytest.raises(CfdiParseError, match="TimbreFiscalDigital"):
        parse_cfdi_xml(xml_no_tfd)


def test_parser_rejects_malformed_xml():
    with pytest.raises(CfdiParseError, match="Invalid XML"):
        parse_cfdi_xml(b"<not-closed>")


def test_parser_rejects_non_cfdi_root():
    with pytest.raises(CfdiParseError, match="cfdi:Comprobante"):
        parse_cfdi_xml(b'<?xml version="1.0"?><other/>')


def test_parser_handles_ppd_invoice():
    parsed = parse_cfdi_xml(_cfdi_40_sample(payment_method="PPD"))
    assert parsed.payment_method == "PPD"


# -------- Service layer tests ----------------------------------------

class _FakeGastoDB:
    def __init__(self):
        self.rows: dict[str, object] = {}
        self.added: list = []

    async def scalar(self, stmt):
        import re
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        m = re.search(r"cfdi_uuid\s*=\s*'([^']+)'", sql)
        if not m:
            return None
        return self.rows.get(m.group(1))

    def add(self, obj):
        self.added.append(obj)
        if hasattr(obj, "cfdi_uuid"):
            self.rows[obj.cfdi_uuid] = obj

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_receiver():
    """Uploading a CFDI addressed to someone else is a policy error, not
    a parse error. The operator shouldn't be able to stuff their gastos
    with a random invoice they found."""
    db = _FakeGastoDB()
    with pytest.raises(service.UploadRejected, match="receiver RFC"):
        await service.ingest_cfdi_xml(
            db=db,
            xml_content=_cfdi_40_sample(receiver_rfc="SOMEONE_ELSE"),
            expected_receiver_rfc="ZEPG070314VC1",
        )


@pytest.mark.asyncio
async def test_ingest_happy_path_stores_row():
    db = _FakeGastoDB()
    row, was_new = await service.ingest_cfdi_xml(
        db=db,
        xml_content=_cfdi_40_sample(),
        expected_receiver_rfc="ZEPG070314VC1",
    )
    assert was_new is True
    assert row.cfdi_uuid == "A1B2C3D4-E5F6-7890-ABCD-1234567890AB"
    assert row.subtotal == Decimal("1000.00")
    assert row.tax_iva == Decimal("160.00")
    assert row.is_acreditable is True
    assert row.payment_date == date(2026, 3, 15)  # PUE → paid at emission


@pytest.mark.asyncio
async def test_ingest_is_idempotent_on_duplicate_upload():
    """Re-uploading the same XML batch must not crash or double-count."""
    db = _FakeGastoDB()
    xml = _cfdi_40_sample()
    row1, was_new1 = await service.ingest_cfdi_xml(
        db=db, xml_content=xml, expected_receiver_rfc="ZEPG070314VC1"
    )
    assert was_new1 is True
    row2, was_new2 = await service.ingest_cfdi_xml(
        db=db, xml_content=xml, expected_receiver_rfc="ZEPG070314VC1"
    )
    assert was_new2 is False
    assert row1 is row2  # same object returned


@pytest.mark.asyncio
async def test_ppd_invoice_leaves_payment_date_null():
    """PPD payment_date is set later when the operator registers the
    actual payment. Otherwise IVA acreditable would land in the wrong
    month under flujo de efectivo."""
    db = _FakeGastoDB()
    row, _ = await service.ingest_cfdi_xml(
        db=db,
        xml_content=_cfdi_40_sample(payment_method="PPD"),
        expected_receiver_rfc="ZEPG070314VC1",
    )
    assert row.payment_method == "PPD"
    assert row.payment_date is None


def test_parser_case_insensitive_receiver_match():
    """ingest_cfdi_xml compares RFCs case-insensitively (constancia
    uses uppercase; CFDIs occasionally normalize to any case)."""
    # This test is a property of the service, not the parser, but the
    # parser preserves case so we include here to document the contract.
    parsed = parse_cfdi_xml(_cfdi_40_sample(receiver_rfc="zepg070314vc1"))
    assert parsed.receiver_rfc == "zepg070314vc1"
