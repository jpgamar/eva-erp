"""Business logic for the gastos module."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.facturas_recibidas.models import FacturaRecibida
from src.facturas_recibidas.xml_parser import CfdiParseError, parse_cfdi_xml

logger = logging.getLogger(__name__)


class UploadRejected(Exception):
    """Raised when an uploaded XML cannot be stored (wrong RFC, malformed, etc.)."""


async def ingest_cfdi_xml(
    db: AsyncSession,
    *,
    xml_content: bytes | str,
    expected_receiver_rfc: str,
    user_id: uuid.UUID | None = None,
) -> tuple[FacturaRecibida, bool]:
    """Parse, validate and store one CFDI XML.

    Returns ``(row, was_new)``. If the XML's UUID is already in the
    database, returns the existing row and ``False`` (idempotent).

    Raises ``UploadRejected`` when the document isn't eligible:
      * malformed XML / missing UUID / wrong namespace
      * receiver RFC doesn't match ``expected_receiver_rfc`` — this
        prevents an operator from accidentally uploading someone else's
        CFDI as theirs
    """
    try:
        parsed = parse_cfdi_xml(xml_content)
    except CfdiParseError as exc:
        raise UploadRejected(f"Invalid CFDI XML: {exc}") from exc

    if parsed.receiver_rfc.upper() != expected_receiver_rfc.upper():
        raise UploadRejected(
            f"CFDI receiver RFC {parsed.receiver_rfc!r} does not match "
            f"expected {expected_receiver_rfc!r} — refusing to store a "
            f"CFDI addressed to another taxpayer."
        )

    # Dedupe by UUID (SAT-unique identifier). Operator can re-upload a
    # batch safely; no crash, no duplicates.
    existing = await db.scalar(
        select(FacturaRecibida).where(FacturaRecibida.cfdi_uuid == parsed.cfdi_uuid)
    )
    if existing:
        return existing, False

    xml_text = (
        xml_content.decode("utf-8", errors="replace")
        if isinstance(xml_content, bytes)
        else xml_content
    )

    # payment_date: defaults to issue_date for PUE (paid at emission).
    # For PPD we leave null — operator sets it when the actual payment
    # happens (otherwise IVA acreditable would be counted in the wrong
    # month under flujo de efectivo).
    default_payment_date = (
        parsed.issue_date.date() if parsed.payment_method == "PUE" else None
    )

    row = FacturaRecibida(
        cfdi_uuid=parsed.cfdi_uuid,
        issuer_rfc=parsed.issuer_rfc,
        issuer_legal_name=parsed.issuer_legal_name,
        issuer_tax_system=parsed.issuer_tax_system,
        receiver_rfc=parsed.receiver_rfc,
        receiver_legal_name=parsed.receiver_legal_name,
        issue_date=parsed.issue_date,
        payment_date=default_payment_date,
        currency=parsed.currency,
        exchange_rate=parsed.exchange_rate,
        subtotal=parsed.subtotal,
        tax_iva=parsed.tax_iva,
        tax_ieps=parsed.tax_ieps,
        iva_retention=parsed.iva_retention,
        isr_retention=parsed.isr_retention,
        total=parsed.total,
        cfdi_type=parsed.cfdi_type,
        cfdi_use=parsed.cfdi_use,
        payment_form=parsed.payment_form,
        payment_method=parsed.payment_method,
        xml_content=xml_text,
        sat_status="unknown",
        is_acreditable=True,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row, True


async def list_gastos(
    db: AsyncSession,
    *,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    acreditable_only: bool = False,
) -> list[FacturaRecibida]:
    stmt = select(FacturaRecibida).order_by(FacturaRecibida.issue_date.desc())
    conditions = []
    if year is not None and month is not None:
        # When filtering by a specific month, also surface rows with
        # payment_date=NULL. Those are PPD gastos the operator hasn't
        # yet marked as paid — hiding them means the operator never
        # sees them, and the IVA acreditable never reaches the
        # declaración. (Codex P2, 2026-04-18.)
        period_match = and_(
            extract("year", FacturaRecibida.payment_date) == year,
            extract("month", FacturaRecibida.payment_date) == month,
        )
        conditions.append(
            or_(
                period_match,
                FacturaRecibida.payment_date.is_(None),
            )
        )
    elif year is not None:
        conditions.append(extract("year", FacturaRecibida.payment_date) == year)
    elif month is not None:
        conditions.append(extract("month", FacturaRecibida.payment_date) == month)
    if category:
        conditions.append(FacturaRecibida.category == category)
    if acreditable_only:
        conditions.append(FacturaRecibida.is_acreditable.is_(True))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_iva_acreditable(
    db: AsyncSession, *, year: int, month: int
) -> tuple[Decimal, int]:
    """Sum of IVA acreditable for a calendar month.

    RESICO flujo de efectivo: IVA is acreditable in the month the gasto
    was effectively paid (``payment_date``), not when the CFDI was issued.

    Filters:
      * ``is_acreditable=True`` (operator hasn't flagged as personal)
      * cfdi_type not in ('E', 'P') — egresos and complements cancel out
        or don't represent new IVA

    Returns (total_iva, count_of_rows_included).
    """
    stmt = (
        select(
            func.coalesce(func.sum(FacturaRecibida.tax_iva), 0),
            func.count(FacturaRecibida.id),
        )
        .where(extract("year", FacturaRecibida.payment_date) == year)
        .where(extract("month", FacturaRecibida.payment_date) == month)
        .where(FacturaRecibida.is_acreditable.is_(True))
        .where(FacturaRecibida.cfdi_type == "I")
    )
    result = await db.execute(stmt)
    total_iva, row_count = result.one()
    return Decimal(total_iva or 0), int(row_count or 0)
