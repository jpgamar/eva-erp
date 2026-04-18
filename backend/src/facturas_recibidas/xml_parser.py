"""Pure-stdlib parser for CFDI XML (v3.3 and v4.0).

SAT changed the namespace between 3.3 and 4.0 but the document shape
is almost identical — both have cfdi:Comprobante with cfdi:Emisor,
cfdi:Receptor, cfdi:Conceptos, cfdi:Impuestos, and a
tfd:TimbreFiscalDigital inside cfdi:Complemento.

This parser intentionally avoids lxml and third-party XML libs to
keep the dependency tree small. ``xml.etree.ElementTree`` is enough
for the structure we need.

Reference: https://www.sat.gob.mx/consulta/35025/formato-de-factura-electronica-(anexo-20)
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable


CFDI_NAMESPACES = {
    "cfdi_40": "http://www.sat.gob.mx/cfd/4",
    "cfdi_33": "http://www.sat.gob.mx/cfd/3",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

_IMPUESTO_ISR = "001"
_IMPUESTO_IVA = "002"
_IMPUESTO_IEPS = "003"


class CfdiParseError(Exception):
    """Raised when the XML is not a recognizable CFDI."""


@dataclass
class ParsedCfdi:
    cfdi_uuid: str
    cfdi_type: str  # 'I', 'E', 'P', 'N', 'T'
    issue_date: datetime
    issuer_rfc: str
    issuer_legal_name: str
    issuer_tax_system: str | None
    receiver_rfc: str
    receiver_legal_name: str | None
    currency: str
    exchange_rate: Decimal | None
    subtotal: Decimal
    total: Decimal
    tax_iva: Decimal
    tax_ieps: Decimal
    iva_retention: Decimal
    isr_retention: Decimal
    cfdi_use: str | None
    payment_form: str | None
    payment_method: str | None


def _detect_namespace(root: ET.Element) -> str:
    """Return the CFDI namespace URI for this document.

    ElementTree stores namespaces in the tag as ``{uri}localname``; we
    read the root tag to decide whether it's 3.3 or 4.0 and the parser
    uses the returned URI for every subsequent findall.
    """
    m = re.match(r"\{(.+?)\}Comprobante$", root.tag)
    if not m:
        raise CfdiParseError(
            f"Root element is not a cfdi:Comprobante (got {root.tag!r})"
        )
    uri = m.group(1)
    if uri not in (CFDI_NAMESPACES["cfdi_40"], CFDI_NAMESPACES["cfdi_33"]):
        raise CfdiParseError(f"Unknown CFDI namespace: {uri}")
    return uri


def _find(root: ET.Element, cfdi_ns: str, path: str) -> ET.Element | None:
    """Find one element at an xpath, substituting the cfdi namespace URI."""
    prefixed = path.replace("cfdi:", f"{{{cfdi_ns}}}")
    return root.find(prefixed)


def _findall(root: ET.Element, cfdi_ns: str, path: str) -> Iterable[ET.Element]:
    prefixed = path.replace("cfdi:", f"{{{cfdi_ns}}}")
    return root.findall(prefixed)


def _decimal(s: str | None) -> Decimal:
    return Decimal(s) if s is not None else Decimal("0")


def _sum_tax(elements: Iterable[ET.Element], impuesto_code: str) -> Decimal:
    """Sum ``Importe`` over tax elements matching the ``Impuesto`` code."""
    total = Decimal("0")
    for el in elements:
        if el.get("Impuesto") == impuesto_code:
            total += _decimal(el.get("Importe"))
    return total


def parse_cfdi_xml(xml_bytes: bytes | str) -> ParsedCfdi:
    """Parse a CFDI XML blob into a ``ParsedCfdi`` dataclass.

    Raises ``CfdiParseError`` on malformed XML or missing required
    fields. The caller is responsible for matching ``receiver_rfc``
    against the expected RFC (rejecting mis-addressed uploads is a
    *policy* decision, not a parser concern).
    """
    if isinstance(xml_bytes, bytes):
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise CfdiParseError(f"Invalid XML: {exc}") from exc
    else:
        try:
            root = ET.fromstring(xml_bytes.encode("utf-8"))
        except ET.ParseError as exc:
            raise CfdiParseError(f"Invalid XML: {exc}") from exc

    cfdi_ns = _detect_namespace(root)

    # Comprobante attributes
    total = _decimal(root.get("Total"))
    subtotal = _decimal(root.get("SubTotal"))
    currency = root.get("Moneda") or "MXN"
    exchange = root.get("TipoCambio")
    exchange_rate = Decimal(exchange) if exchange else None
    issue_date_str = root.get("Fecha")
    if not issue_date_str:
        raise CfdiParseError("Comprobante missing Fecha attribute")
    # SAT Anexo 20 stores "Fecha" as local Mexico City time without a tz
    # suffix. Some CFDIs (mostly test fixtures) do include Z or ±HH:MM.
    # Normalize both cases: parse what's there, then stamp UTC when the
    # source was naive. Shifting a naive timestamp to UTC keeps the
    # wall-clock but adds a timezone — fine for audit trails and enough
    # resolution for declaración math (which aggregates by date only).
    iso_str = issue_date_str.replace("Z", "+00:00")
    try:
        issue_date = datetime.fromisoformat(iso_str)
    except ValueError as exc:
        raise CfdiParseError(f"Invalid Fecha attribute: {issue_date_str!r}") from exc
    if issue_date.tzinfo is None:
        issue_date = issue_date.replace(tzinfo=timezone.utc)
    cfdi_type = root.get("TipoDeComprobante") or "I"
    payment_form = root.get("FormaPago")
    payment_method = root.get("MetodoPago")

    # Emisor
    emisor = _find(root, cfdi_ns, "cfdi:Emisor")
    if emisor is None:
        raise CfdiParseError("CFDI has no cfdi:Emisor element")
    issuer_rfc = emisor.get("Rfc") or ""
    issuer_legal_name = emisor.get("Nombre") or ""
    issuer_tax_system = emisor.get("RegimenFiscal")

    # Receptor
    receptor = _find(root, cfdi_ns, "cfdi:Receptor")
    if receptor is None:
        raise CfdiParseError("CFDI has no cfdi:Receptor element")
    receiver_rfc = receptor.get("Rfc") or ""
    receiver_legal_name = receptor.get("Nombre")
    cfdi_use = receptor.get("UsoCFDI")

    # Impuestos — sum IVA/IEPS traslados (supplier charged us) and any retenciones.
    traslados = list(_findall(root, cfdi_ns, "cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado"))
    retenciones = list(_findall(root, cfdi_ns, "cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion"))

    # CFDI 4.0 sometimes has no global Impuestos block; taxes only live
    # under each Concepto. Fall back to summing per-concepto.
    if not traslados:
        traslados = list(
            _findall(root, cfdi_ns, "cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado")
        )
    if not retenciones:
        retenciones = list(
            _findall(root, cfdi_ns, "cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion")
        )

    tax_iva = _sum_tax(traslados, _IMPUESTO_IVA)
    tax_ieps = _sum_tax(traslados, _IMPUESTO_IEPS)
    iva_retention = _sum_tax(retenciones, _IMPUESTO_IVA)
    isr_retention = _sum_tax(retenciones, _IMPUESTO_ISR)

    # TFD (UUID)
    tfd = root.find(
        f"{{{cfdi_ns}}}Complemento/{{{CFDI_NAMESPACES['tfd']}}}TimbreFiscalDigital"
    )
    if tfd is None:
        raise CfdiParseError("CFDI has no TimbreFiscalDigital (not stamped)")
    cfdi_uuid = tfd.get("UUID") or ""
    if not cfdi_uuid:
        raise CfdiParseError("TimbreFiscalDigital missing UUID")

    return ParsedCfdi(
        cfdi_uuid=cfdi_uuid,
        cfdi_type=cfdi_type,
        issue_date=issue_date,
        issuer_rfc=issuer_rfc,
        issuer_legal_name=issuer_legal_name,
        issuer_tax_system=issuer_tax_system,
        receiver_rfc=receiver_rfc,
        receiver_legal_name=receiver_legal_name,
        currency=currency,
        exchange_rate=exchange_rate,
        subtotal=subtotal,
        total=total,
        tax_iva=tax_iva,
        tax_ieps=tax_ieps,
        iva_retention=iva_retention,
        isr_retention=isr_retention,
        cfdi_use=cfdi_use,
        payment_form=payment_form,
        payment_method=payment_method,
    )
