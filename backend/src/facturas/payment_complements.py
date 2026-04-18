"""Business logic for Complementos de Pago (CFDI tipo P).

The UI calls ``register_payment`` which creates a ``cfdi_payments`` row
in ``status='pending_stamp'`` and commits. The outbox worker picks it
up on its next cycle and calls FacturAPI with the idempotency key.

Separate from ``facturas/service.py`` because the complemento workflow
has its own invariants (payment can't exceed outstanding balance, only
PPD facturas are eligible, and the SAT 5-day deadline needs explicit
tracking).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.facturas.models import CfdiPayment, Factura
from src.facturas.schemas import CfdiPaymentCreate

logger = logging.getLogger(__name__)


async def register_payment(
    db: AsyncSession,
    factura_id: uuid.UUID,
    data: CfdiPaymentCreate,
    user_id: uuid.UUID | None = None,
) -> CfdiPayment:
    """Validate + insert a pending CFDI tipo P row.

    Raises HTTPException on invalid preconditions so the router returns
    a helpful 4xx. Commits are the caller's responsibility (the router
    dependency ``get_db`` handles that at request end).
    """
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura not found")
    if factura.status != "valid":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot register payment against a factura in status '{factura.status}'",
        )
    if factura.payment_method != "PPD":
        raise HTTPException(
            status_code=400,
            detail="Complementos de pago only apply to PPD (pago en parcialidades) facturas",
        )

    total_due = factura.total or Decimal("0")
    total_paid = factura.total_paid or Decimal("0")
    outstanding = total_due - total_paid
    if data.payment_amount > outstanding + Decimal("0.005"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Payment {data.payment_amount} exceeds outstanding balance "
                f"{outstanding} on factura {factura_id}"
            ),
        )

    # last_balance on the FIRST installment must equal the invoice total per
    # SAT spec; on subsequent installments it's the balance before this
    # payment. Callers may pass it in, but we also compute a sensible default.
    default_last_balance = total_due if data.installment == 1 else (outstanding)
    last_balance = data.last_balance if data.last_balance is not None else default_last_balance

    payment = CfdiPayment(
        id=uuid.uuid4(),
        factura_id=factura.id,
        payment_date=data.payment_date,
        payment_form=data.payment_form,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        payment_amount=Decimal(str(data.payment_amount)),
        last_balance=last_balance,
        installment=data.installment,
        status="pending_stamp",
        stamp_retry_count=0,
        facturapi_idempotency_key=None,  # set when outbox first attempts
        created_by=user_id,
    )
    db.add(payment)
    await db.flush()
    payment.facturapi_idempotency_key = f"pago:{payment.id}"
    await db.flush()

    # Optimistically bump the factura's cached totals. If the outbox stamp
    # later fails permanently, a reconciliation / admin action will roll back.
    # For the *common* case (stamping succeeds) these numbers match reality
    # without waiting for a roundtrip.
    factura.total_paid = (total_paid + payment.payment_amount).quantize(Decimal("0.01"))
    factura.payment_status = _derive_payment_status(factura.total, factura.total_paid)
    db.add(factura)
    await db.flush()
    return payment


def _derive_payment_status(total: Decimal | None, total_paid: Decimal | None) -> str:
    """Map (total, total_paid) into a bucket for quick filtering.

    Uses a 1-cent tolerance because the SAT complement tax rebuild can
    introduce sub-cent float noise on long installment plans.
    """
    total = Decimal(str(total or 0))
    total_paid = Decimal(str(total_paid or 0))
    if total_paid <= Decimal("0.00"):
        return "unpaid"
    if total_paid + Decimal("0.01") >= total:
        return "paid"
    return "partial"


def days_until_sat_deadline(payment_date: date, today: date | None = None) -> int:
    """Return days remaining before the SAT 5-of-next-month deadline
    for a given payment_date. Negative if already overdue.

    Example: payment_date = 2026-03-23 → deadline = 2026-04-05 →
    on 2026-04-01 this returns 4, on 2026-04-07 returns -2.
    """
    today = today or datetime.now(timezone.utc).date()
    # 5th day of month following payment_date.
    y, m = payment_date.year, payment_date.month + 1
    if m == 13:
        y, m = y + 1, 1
    deadline = date(y, m, 5)
    return (deadline - today).days


async def list_payments_for_factura(
    db: AsyncSession, factura_id: uuid.UUID
) -> list[CfdiPayment]:
    stmt = (
        select(CfdiPayment)
        .where(CfdiPayment.factura_id == factura_id)
        .order_by(CfdiPayment.payment_date.asc(), CfdiPayment.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
