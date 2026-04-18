"""Monthly declaración calculator for RESICO PF.

Aggregates ingresos (from ``facturas`` + ``cfdi_payments``), retenciones,
and IVA acreditable (from ``facturas_recibidas``) into the numbers
the operator types into the SAT portal.

Per LISR Art 113-E, RESICO PF is pure flujo de efectivo:
  * An ingreso is counted in the month when the money was received,
    not when the CFDI was issued. For PUE the CFDI date stands in
    (SAT treats emission = payment). For PPD the ingreso is counted
    via the ``cfdi_payments`` row, in the month of ``payment_date``.
  * IVA acreditable of a gasto is counted in the month the gasto was
    effectively paid (``facturas_recibidas.payment_date``).

No ISR deductions — RESICO explicitly excludes them. So our ISR calc
is just ``ingresos × tasa_tabla``, minus retenciones already paid by PMs.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.declaracion.schemas import (
    DeclaracionResponse,
    DeclaracionWarning,
    IsrResicoPf,
    IvaSimplificado,
)
from src.declaracion.tables import resico_pf_rate_for
from src.facturas.models import CfdiPayment, Factura
from src.facturas_recibidas.models import FacturaRecibida

logger = logging.getLogger(__name__)


def _round(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _sum_pue_ingresos(
    db: AsyncSession, *, year: int, month: int
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Sum (subtotal, iva_trasladado, isr_retention, iva_retention,
    local_retention) over PUE facturas valid in the period.

    PUE is treated as cobrado-at-emission per SAT convention — we
    filter by ``issued_at`` month, not ``created_at``.
    """
    stmt = (
        select(
            func.coalesce(func.sum(Factura.subtotal), 0),
            func.coalesce(func.sum(Factura.tax), 0),
            func.coalesce(func.sum(Factura.isr_retention), 0),
            func.coalesce(func.sum(Factura.iva_retention), 0),
        )
        .where(Factura.status == "valid")
        .where(Factura.payment_method == "PUE")
        .where(extract("year", Factura.issued_at) == year)
        .where(extract("month", Factura.issued_at) == month)
    )
    result = await db.execute(stmt)
    subtotal, tax, isr_ret, iva_ret = result.one()
    return Decimal(subtotal), Decimal(tax), Decimal(isr_ret), Decimal(iva_ret)


async def _sum_ppd_payments(
    db: AsyncSession, *, year: int, month: int
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """For PPD, the ingreso + IVA + retenciones are distributed across
    the cfdi_payments by payment_date. Each payment carries its
    proportion of the original factura's retentions.

    We compute this on the fly: factor = payment_amount / factura.total.
    """
    # Join CfdiPayment → Factura to prorate retenciones.
    stmt = (
        select(
            CfdiPayment.payment_amount,
            Factura.total,
            Factura.subtotal,
            Factura.tax,
            Factura.isr_retention,
            Factura.iva_retention,
        )
        .join(Factura, Factura.id == CfdiPayment.factura_id)
        .where(CfdiPayment.status == "valid")
        .where(extract("year", CfdiPayment.payment_date) == year)
        .where(extract("month", CfdiPayment.payment_date) == month)
    )
    result = await db.execute(stmt)
    sub_total = Decimal("0")
    iva_total = Decimal("0")
    isr_ret_total = Decimal("0")
    iva_ret_total = Decimal("0")
    for payment_amount, factura_total, factura_sub, factura_tax, factura_isr, factura_iva_ret in result.all():
        factura_total = Decimal(factura_total or 0)
        if factura_total <= 0:
            continue
        factor = Decimal(str(payment_amount)) / factura_total
        sub_total += Decimal(factura_sub or 0) * factor
        iva_total += Decimal(factura_tax or 0) * factor
        isr_ret_total += Decimal(factura_isr or 0) * factor
        iva_ret_total += Decimal(factura_iva_ret or 0) * factor
    return sub_total, iva_total, isr_ret_total, iva_ret_total


async def _sum_iva_acreditable(db: AsyncSession, *, year: int, month: int) -> Decimal:
    """IVA acreditable = sum of tax_iva on received CFDIs paid in the
    month, marked acreditable, type I (ingreso). Egresos (E) and
    complements (P) are excluded.
    """
    stmt = (
        select(func.coalesce(func.sum(FacturaRecibida.tax_iva), 0))
        .where(extract("year", FacturaRecibida.payment_date) == year)
        .where(extract("month", FacturaRecibida.payment_date) == month)
        .where(FacturaRecibida.is_acreditable.is_(True))
        .where(FacturaRecibida.cfdi_type == "I")
    )
    result = await db.execute(stmt)
    return Decimal(result.scalar_one() or 0)


async def _collect_warnings(
    db: AsyncSession, *, year: int, month: int
) -> list[DeclaracionWarning]:
    warnings: list[DeclaracionWarning] = []

    # Blocker: any PPD factura cobrada este mes cuyo complemento sigue
    # pendiente. Si no se timbra antes del día 5 siguiente, SAT multa.
    pending_stmt = (
        select(func.count(CfdiPayment.id))
        .where(CfdiPayment.status.in_(["pending_stamp", "stamp_failed"]))
        .where(extract("year", CfdiPayment.payment_date) == year)
        .where(extract("month", CfdiPayment.payment_date) == month)
    )
    pending_payments = int((await db.execute(pending_stmt)).scalar_one() or 0)
    if pending_payments:
        warnings.append(
            DeclaracionWarning(
                severity="blocker",
                code="pending_payment_complement",
                message=(
                    f"{pending_payments} payment(s) received this month still have "
                    "no Complemento de Pago. Stamp them before the 5th of the "
                    "next month to avoid SAT penalties."
                ),
            )
        )

    # Warning: any stamp_failed facturas this month
    failed_stmt = (
        select(func.count(Factura.id))
        .where(Factura.status == "stamp_failed")
        .where(extract("year", Factura.issued_at) == year)
        .where(extract("month", Factura.issued_at) == month)
    )
    failed_facturas = int((await db.execute(failed_stmt)).scalar_one() or 0)
    if failed_facturas:
        warnings.append(
            DeclaracionWarning(
                severity="warning",
                code="stamp_failed_facturas",
                message=(
                    f"{failed_facturas} factura(s) this month failed to stamp "
                    "after retries. These will NOT appear in SAT's prefill and "
                    "need manual remediation."
                ),
            )
        )

    return warnings


async def compute_monthly_declaration(
    db: AsyncSession, *, year: int, month: int, rfc: str
) -> DeclaracionResponse:
    """Compute the full declaración for a given month.

    The numbers returned match 1-to-1 what the operator types into the
    SAT portal's ISR simplificado + IVA simplificado tabs. See the test
    suite for the F-4 + March 2026 golden case.
    """
    pue_sub, pue_iva, pue_isr_ret, pue_iva_ret = await _sum_pue_ingresos(
        db, year=year, month=month
    )
    ppd_sub, ppd_iva, ppd_isr_ret, ppd_iva_ret = await _sum_ppd_payments(
        db, year=year, month=month
    )
    iva_acreditable = await _sum_iva_acreditable(db, year=year, month=month)

    ingresos = _round(pue_sub + ppd_sub)
    iva_trasladado = _round(pue_iva + ppd_iva)
    isr_retenido = _round(pue_isr_ret + ppd_isr_ret)
    iva_retenido = _round(pue_iva_ret + ppd_iva_ret)
    iva_acreditable = _round(iva_acreditable)

    # ISR
    tasa = resico_pf_rate_for(ingresos) if ingresos > 0 else Decimal("0")
    impuesto_isr = _round(ingresos * tasa)
    isr_neto = impuesto_isr - isr_retenido
    isr_a_pagar = _round(isr_neto if isr_neto > 0 else Decimal("0"))
    isr_saldo_favor = _round(-isr_neto if isr_neto < 0 else Decimal("0"))

    # IVA
    iva_neto = iva_trasladado - iva_retenido - iva_acreditable
    iva_a_pagar = _round(iva_neto if iva_neto > 0 else Decimal("0"))
    iva_saldo_favor = _round(-iva_neto if iva_neto < 0 else Decimal("0"))

    return DeclaracionResponse(
        year=year,
        month=month,
        rfc=rfc,
        isr=IsrResicoPf(
            ingresos=ingresos,
            tasa=tasa,
            impuesto_mensual=impuesto_isr,
            isr_retenido_por_pms=isr_retenido,
            impuesto_a_pagar=isr_a_pagar,
            saldo_a_favor=isr_saldo_favor,
        ),
        iva=IvaSimplificado(
            actividades_gravadas_16=ingresos,
            iva_trasladado=iva_trasladado,
            iva_retenido_por_pms=iva_retenido,
            iva_acreditable=iva_acreditable,
            impuesto_a_pagar=iva_a_pagar,
            saldo_a_favor=iva_saldo_favor,
        ),
        warnings=await _collect_warnings(db, year=year, month=month),
    )
