"""Dashboard alerts for the declaración workflow.

Returns a rolling list of "things the operator should do right now".
Consumed by the dashboard widget and (in the future) by an email
reminder job. Implementation is read-only and computed on demand —
no storage needed, no new table.

Alert taxonomy
--------------
* **blocker** — must resolve before presenting the declaración. Shown
  in red on the dashboard.
* **warning** — degrades the declaración if unresolved (e.g. missing
  CFDIs for gastos). Yellow.
* **info** — countdowns and reminders without immediate impact. Blue.

Rules
-----
Today is day D of month M. Let PREV = month M − 1 (the period the
declaración is due for this cycle). Alerts:

1. D ≤ 17 & we have ingresos in PREV → info: "Declaración due in X days".
2. D > 17 & declaración of PREV not marked presentada → blocker
   "Declaración is overdue".
3. D ≤ 5 of M & we have cfdi_payments with payment_date in PREV and
   status != valid → blocker "N complementos de pago due by day 5".
4. Any stamp_failed factura/payment anywhere → warning.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.declaracion.schemas import DeclaracionAlert, DeclaracionAlertsResponse
from src.facturas.models import CfdiPayment, Factura


def _prev_month(today: date) -> tuple[int, int]:
    """Return (year, month) for the month before ``today``."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


async def compute_alerts(
    db: AsyncSession, *, today: date | None = None
) -> DeclaracionAlertsResponse:
    today = today or datetime.now(timezone.utc).date()
    alerts: list[DeclaracionAlert] = []

    prev_year, prev_month = _prev_month(today)

    # --- Rule 3: Complementos de Pago pending near SAT's 5-day deadline.
    pending_complements = int(
        (
            await db.execute(
                select(func.count(CfdiPayment.id))
                .where(CfdiPayment.status.in_(["pending_stamp", "stamp_failed"]))
                .where(extract("year", CfdiPayment.payment_date) == prev_year)
                .where(extract("month", CfdiPayment.payment_date) == prev_month)
            )
        ).scalar_one()
        or 0
    )
    if pending_complements:
        days_to_day5 = 5 - today.day if today.month == prev_month + 1 else -1
        severity = "blocker" if today.day >= 3 else "warning"
        message = (
            f"{pending_complements} Complemento(s) de Pago pendientes "
            f"para cobros de {prev_year}-{prev_month:02d}. "
        )
        if days_to_day5 >= 0:
            message += f"Faltan {days_to_day5} día(s) para el límite SAT (día 5)."
        else:
            message += "LÍMITE SAT (día 5) ya venció — posible multa."
        alerts.append(
            DeclaracionAlert(
                severity=severity,
                code="pending_payment_complement",
                message=message,
                deep_link=f"/facturas?filter=pending_payment",
            )
        )

    # --- Rule 1 & 2: Declaración cycle for PREV month.
    ingresos_rows = int(
        (
            await db.execute(
                select(func.count(Factura.id))
                .where(Factura.status == "valid")
                .where(Factura.payment_method == "PUE")
                .where(extract("year", Factura.issued_at) == prev_year)
                .where(extract("month", Factura.issued_at) == prev_month)
            )
        ).scalar_one()
        or 0
    )
    if ingresos_rows:
        if today.day < 17:
            days_left = 17 - today.day
            alerts.append(
                DeclaracionAlert(
                    severity="info",
                    code="declaracion_upcoming",
                    message=(
                        f"Declaración de {prev_year}-{prev_month:02d} vence "
                        f"en {days_left} día(s) (día 17 del mes)."
                    ),
                    deep_link=f"/declaracion/{prev_year}/{prev_month}",
                )
            )
        elif today.day > 17:
            alerts.append(
                DeclaracionAlert(
                    severity="blocker",
                    code="declaracion_overdue",
                    message=(
                        f"Declaración de {prev_year}-{prev_month:02d} VENCIDA. "
                        f"Presentar extemporánea cuanto antes — recargos y "
                        f"multas crecen por día."
                    ),
                    deep_link=f"/declaracion/{prev_year}/{prev_month}",
                )
            )
        # day == 17 → silence (operator already knows, presumably working on it)

    # --- Rule 4: any stamp_failed CFDIs (ingresos or complementos).
    failed_facturas = int(
        (
            await db.execute(
                select(func.count(Factura.id)).where(Factura.status == "stamp_failed")
            )
        ).scalar_one()
        or 0
    )
    failed_payments = int(
        (
            await db.execute(
                select(func.count(CfdiPayment.id)).where(
                    CfdiPayment.status == "stamp_failed"
                )
            )
        ).scalar_one()
        or 0
    )
    total_failed = failed_facturas + failed_payments
    if total_failed:
        alerts.append(
            DeclaracionAlert(
                severity="warning",
                code="stamp_failed",
                message=(
                    f"{total_failed} CFDI(s) abandonados por el outbox tras "
                    f"agotar reintentos. Revisa el runbook de CFDI stamping failure."
                ),
                deep_link="/monitoring",
            )
        )

    return DeclaracionAlertsResponse(today=today.isoformat(), alerts=alerts)
