import uuid
from datetime import date
from decimal import Decimal

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, require_admin
from src.auth.models import User
from src.common.database import get_db
from src.finances.models import (
    CashBalance,
    ExchangeRate,
    Expense,
    IncomeEntry,
    Invoice,
    ManualDepositEntry,
    StripePaymentEvent,
    StripePayoutEvent,
)
from src.finances.recurrence import (
    build_income_metadata,
    extract_income_recurrence,
    income_monthly_equivalent,
    income_monthly_mrr_equivalent,
    normalize_income_recurrence_payload,
)
from src.finances.schemas import (
    CashBalanceCreate,
    CashBalanceResponse,
    ExchangeRateResponse,
    ExchangeRateUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseSummary,
    ExpenseUpdate,
    IncomeCreate,
    IncomeResponse,
    IncomeSummary,
    IncomeUpdate,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
    ManualDepositCreate,
    ManualDepositResponse,
    PartnerSummary,
    FinanceParityCheckResponse,
    StripeLinkEventRequest,
    StripeLinkEventResponse,
    StripeReconcileRequest,
    StripeReconcileResponse,
    StripeReconciliationSummary,
    StripeUnlinkedEventsResponse,
    StripeWebhookAckResponse,
)
from src.finances.stripe_service import apply_stripe_event, reconcile_stripe_events, verify_and_parse_webhook

router = APIRouter(prefix="/finances", tags=["finances"])

DEFAULT_RATE = Decimal("0.05")
ALLOWED_MANUAL_PAYMENT_REASONS = {"offline_transfer", "cash", "adjustment", "correction"}
ALLOWED_MANUAL_DEPOSIT_REASONS = {"manual_bank_deposit", "adjustment"}


async def _get_mxn_to_usd(db: AsyncSession) -> Decimal:
    """Get MXN→USD rate. Looks up stored USD→MXN rate and inverts it."""
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if rate and rate.rate > 0:
        return round(Decimal("1") / rate.rate, 6)
    return DEFAULT_RATE


def _to_usd(amount: Decimal, currency: str, rate: Decimal) -> Decimal:
    if currency == "USD":
        return amount
    return round(amount * rate, 2)


def _to_mxn(amount: Decimal, currency: str, usd_to_mxn: Decimal) -> Decimal:
    if currency == "USD":
        return round(amount * usd_to_mxn, 2)
    return amount


def _normalize_manual_payment_reason(value: str | None) -> str:
    reason = str(value or "offline_transfer").strip().lower()
    if reason not in ALLOWED_MANUAL_PAYMENT_REASONS:
        raise HTTPException(status_code=422, detail="Invalid manual_reason")
    return reason


def _extract_manual_payment_reason(metadata_json: dict | None) -> str:
    if isinstance(metadata_json, dict):
        raw = str(metadata_json.get("manual_reason") or "offline_transfer").strip().lower()
        return raw if raw in ALLOWED_MANUAL_PAYMENT_REASONS else "offline_transfer"
    return "offline_transfer"


def _normalize_manual_deposit_reason(value: str) -> str:
    reason = str(value or "").strip().lower()
    if reason not in ALLOWED_MANUAL_DEPOSIT_REASONS:
        raise HTTPException(status_code=422, detail="Invalid manual deposit reason")
    return reason


def _resolve_period(period: str | None) -> tuple[str, date, date]:
    today = date.today()
    if period is None:
        start = today.replace(day=1)
    else:
        try:
            start = date.fromisoformat(f"{period}-01")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid period format. Expected YYYY-MM") from exc
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return start.strftime("%Y-%m"), start, next_month


def _income_key_for_payment_event(event: StripePaymentEvent) -> str:
    if event.stripe_event_type == "payment_intent.succeeded":
        return f"pi:{event.stripe_payment_intent_id or event.stripe_event_id}"
    return f"refund:{event.stripe_refund_id or event.stripe_charge_id or event.stripe_event_id}"


def _serialize_income(entry: IncomeEntry) -> IncomeResponse:
    recurrence_type, custom_interval_months = extract_income_recurrence(entry.metadata_json, entry.is_recurring)
    monthly_amount_usd = income_monthly_mrr_equivalent(entry.amount_usd, recurrence_type, custom_interval_months)
    return IncomeResponse(
        id=entry.id,
        source=entry.source,
        stripe_payment_id=entry.stripe_payment_id,
        customer_id=entry.customer_id,
        account_id=entry.account_id,
        description=entry.description,
        amount=entry.amount,
        currency=entry.currency,
        amount_usd=entry.amount_usd,
        category=entry.category,
        date=entry.date,
        is_recurring=entry.is_recurring,
        recurrence_type=recurrence_type,
        custom_interval_months=custom_interval_months,
        manual_reason=_extract_manual_payment_reason(entry.metadata_json),
        monthly_amount_usd=monthly_amount_usd,
        created_at=entry.created_at,
    )


# ─── Exchange Rate ────────────────────────────────────────────────

@router.get("/exchange-rates/current", response_model=ExchangeRateResponse)
async def get_current_rate(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if not rate:
        # Return default
        rate = ExchangeRate(
            from_currency="USD", to_currency="MXN",
            rate=DEFAULT_RATE, effective_date=date.today(), source="default"
        )
    return rate


@router.patch("/exchange-rates", response_model=ExchangeRateResponse)
async def update_rate(
    data: ExchangeRateUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    rate = ExchangeRate(
        from_currency="USD", to_currency="MXN",
        rate=data.rate,
        effective_date=data.effective_date or date.today(),
        source="manual",
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return rate


# ─── Income ───────────────────────────────────────────────────────

@router.get("/income", response_model=list[IncomeResponse])
async def list_income(
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    category: str | None = None,
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(IncomeEntry).order_by(IncomeEntry.date.desc())
    if start_date:
        q = q.where(IncomeEntry.date >= start_date)
    if end_date:
        q = q.where(IncomeEntry.date <= end_date)
    if source:
        q = q.where(IncomeEntry.source == source)
    if category:
        q = q.where(IncomeEntry.category == category)
    if account_id:
        q = q.where(IncomeEntry.account_id == account_id)
    result = await db.execute(q)
    entries = result.scalars().all()
    return [_serialize_income(entry) for entry in entries]


@router.post("/income", response_model=IncomeResponse, status_code=201)
async def create_income(
    data: IncomeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate = await _get_mxn_to_usd(db)
    manual_reason = _normalize_manual_payment_reason(data.manual_reason)
    try:
        recurrence_type, custom_interval_months, normalized_recurring = normalize_income_recurrence_payload(
            recurrence_type=data.recurrence_type,
            custom_interval_months=data.custom_interval_months,
            is_recurring=data.is_recurring,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    entry = IncomeEntry(
        source="manual",
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        amount_usd=_to_usd(data.amount, data.currency, rate),
        category=data.category,
        date=data.date,
        is_recurring=normalized_recurring,
        metadata_json=build_income_metadata({"manual_reason": manual_reason}, recurrence_type, custom_interval_months),
        customer_id=data.customer_id,
        account_id=data.account_id,
        created_by=user.id,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return _serialize_income(entry)


@router.patch("/income/{income_id}", response_model=IncomeResponse)
async def update_income(
    income_id: uuid.UUID,
    data: IncomeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(IncomeEntry).where(IncomeEntry.id == income_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Income entry not found")
    if entry.source != "manual":
        raise HTTPException(status_code=400, detail="Cannot edit Stripe-synced entries")

    rate = await _get_mxn_to_usd(db)
    payload = data.model_dump(exclude_unset=True)
    recurrence_type = payload.pop("recurrence_type", None) if "recurrence_type" in payload else None
    custom_interval_months = (
        payload.pop("custom_interval_months", None) if "custom_interval_months" in payload else None
    )
    recurring_flag = payload.pop("is_recurring", None) if "is_recurring" in payload else None
    manual_reason = payload.pop("manual_reason", None) if "manual_reason" in payload else None

    for field, value in payload.items():
        setattr(entry, field, value)

    if any(field in data.model_fields_set for field in {"recurrence_type", "custom_interval_months", "is_recurring"}):
        try:
            normalized_type, normalized_interval, normalized_recurring = normalize_income_recurrence_payload(
                recurrence_type=recurrence_type,
                custom_interval_months=custom_interval_months,
                is_recurring=recurring_flag,
                existing_metadata=entry.metadata_json,
                existing_is_recurring=entry.is_recurring,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        entry.is_recurring = normalized_recurring
        entry.metadata_json = build_income_metadata(entry.metadata_json, normalized_type, normalized_interval)

    if "manual_reason" in data.model_fields_set:
        normalized_reason = _normalize_manual_payment_reason(manual_reason)
        metadata = dict(entry.metadata_json or {})
        metadata["manual_reason"] = normalized_reason
        entry.metadata_json = metadata

    # Recalculate USD
    entry.amount_usd = _to_usd(entry.amount, entry.currency, rate)
    db.add(entry)
    return _serialize_income(entry)


@router.delete("/income/{income_id}")
async def delete_income(
    income_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(IncomeEntry).where(IncomeEntry.id == income_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Income entry not found")
    if entry.source != "manual":
        raise HTTPException(status_code=400, detail="Cannot delete Stripe-synced entries")
    await db.delete(entry)
    return {"message": "Income entry deleted"}


@router.get("/income/summary", response_model=IncomeSummary)
async def income_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # MRR: monthly-equivalent income from recurring entries.
    now = date.today()
    result = await db.execute(select(IncomeEntry))
    entries = result.scalars().all()

    mrr = Decimal("0")
    mrr_by_currency: dict[str, Decimal] = {}
    for entry in entries:
        recurrence_type, custom_interval_months = extract_income_recurrence(entry.metadata_json, entry.is_recurring)
        monthly_native = income_monthly_equivalent(entry.amount, recurrence_type, custom_interval_months)
        if monthly_native > 0:
            mrr_by_currency[entry.currency] = (
                mrr_by_currency.get(entry.currency, Decimal("0")) + monthly_native
            ).quantize(Decimal("0.01"))
        mrr += income_monthly_mrr_equivalent(entry.amount_usd, recurrence_type, custom_interval_months)
    mrr = mrr.quantize(Decimal("0.01"))
    arr = mrr * 12
    arr_by_currency = {
        currency: (value * 12).quantize(Decimal("0.01"))
        for currency, value in mrr_by_currency.items()
    }

    # Total this month (native currency map + legacy USD total)
    total_period = Decimal("0")
    total_period_by_currency: dict[str, Decimal] = {}
    for entry in entries:
        if entry.date.year != now.year or entry.date.month != now.month:
            continue
        total_period += entry.amount_usd
        total_period_by_currency[entry.currency] = (
            total_period_by_currency.get(entry.currency, Decimal("0")) + entry.amount
        ).quantize(Decimal("0.01"))
    total_period = total_period.quantize(Decimal("0.01"))

    return IncomeSummary(
        mrr=mrr, arr=arr,
        total_period=total_period,
        total_period_usd=total_period,
        mrr_by_currency=mrr_by_currency,
        arr_by_currency=arr_by_currency,
        total_period_by_currency=total_period_by_currency,
        mom_growth_pct=None,
    )


# ─── Expenses ─────────────────────────────────────────────────────

@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    paid_by: uuid.UUID | None = None,
    recurring: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Expense).order_by(Expense.date.desc())
    if start_date:
        q = q.where(Expense.date >= start_date)
    if end_date:
        q = q.where(Expense.date <= end_date)
    if category:
        q = q.where(Expense.category == category)
    if paid_by:
        q = q.where(Expense.paid_by == paid_by)
    if recurring is not None:
        q = q.where(Expense.is_recurring == recurring)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/expenses", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate = await _get_mxn_to_usd(db)
    expense = Expense(
        name=data.name,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        amount_usd=_to_usd(data.amount, data.currency, rate),
        category=data.category,
        vendor=data.vendor,
        paid_by=data.paid_by,
        is_recurring=data.is_recurring,
        recurrence=data.recurrence,
        date=data.date,
        vault_credential_id=data.vault_credential_id,
        created_by=user.id,
    )
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    return expense


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    rate = await _get_mxn_to_usd(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    expense.amount_usd = _to_usd(expense.amount, expense.currency, rate)
    db.add(expense)
    return expense


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    await db.delete(expense)
    return {"message": "Expense deleted"}


@router.get("/expenses/summary", response_model=ExpenseSummary)
async def expense_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense))
    expenses = result.scalars().all()

    total_usd = sum(float(e.amount_usd) for e in expenses)
    by_category: dict[str, float] = {}
    by_person: dict[str, float] = {}
    recurring_total = Decimal("0")

    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0) + float(e.amount_usd)
        pid = str(e.paid_by)
        by_person[pid] = by_person.get(pid, 0) + float(e.amount_usd)
        if e.is_recurring:
            recurring_total += e.amount_usd

    return ExpenseSummary(
        total_usd=Decimal(str(total_usd)),
        by_category=by_category,
        by_person=by_person,
        recurring_total_usd=recurring_total,
    )


@router.get("/expenses/partner-summary", response_model=PartnerSummary)
async def partner_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense))
    expenses = result.scalars().all()

    # Get user names
    from src.auth.models import User as UserModel
    users_result = await db.execute(select(UserModel))
    users = {str(u.id): u.name for u in users_result.scalars().all()}

    totals: dict[str, float] = {}
    for e in expenses:
        name = users.get(str(e.paid_by), str(e.paid_by))
        totals[name] = totals.get(name, 0) + float(e.amount_usd)

    return PartnerSummary(partner_totals=totals)


# ─── Stripe Ingestion + Reconciliation ────────────────────────────

@router.post("/stripe/webhook", response_model=StripeWebhookAckResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    try:
        event = verify_and_parse_webhook(payload, stripe_signature)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe event payload") from exc

    status = await apply_stripe_event(db, event, source="webhook")
    return StripeWebhookAckResponse(
        accepted=True,
        event_id=str(event.get("id") or ""),
        event_type=str(event.get("type") or ""),
        status=status,
    )


@router.post("/stripe/reconcile", response_model=StripeReconcileResponse)
async def reconcile_stripe(
    data: StripeReconcileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        stats = await reconcile_stripe_events(
            db,
            backfill=data.backfill,
            start_date=data.start_date,
            end_date=data.end_date,
            max_events=data.max_events,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return StripeReconcileResponse(**stats)


@router.get("/stripe/reconciliation", response_model=StripeReconciliationSummary)
async def stripe_reconciliation_summary(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    period_key, month_start, next_month = _resolve_period(period)

    payments_received = (
        await db.execute(
            select(func.coalesce(func.sum(StripePaymentEvent.amount), 0)).where(
                StripePaymentEvent.stripe_event_type == "payment_intent.succeeded",
                StripePaymentEvent.occurred_at >= month_start,
                StripePaymentEvent.occurred_at < next_month,
            )
        )
    ).scalar() or Decimal("0")

    refunds = (
        await db.execute(
            select(func.coalesce(func.sum(func.abs(StripePaymentEvent.amount)), 0)).where(
                StripePaymentEvent.stripe_event_type == "charge.refunded",
                StripePaymentEvent.occurred_at >= month_start,
                StripePaymentEvent.occurred_at < next_month,
            )
        )
    ).scalar() or Decimal("0")

    payouts_paid = (
        await db.execute(
            select(func.coalesce(func.sum(StripePayoutEvent.amount), 0)).where(
                StripePayoutEvent.status == "paid",
                StripePayoutEvent.paid_at.isnot(None),
                StripePayoutEvent.paid_at >= month_start,
                StripePayoutEvent.paid_at < next_month,
            )
        )
    ).scalar() or Decimal("0")

    payouts_failed = (
        await db.execute(
            select(func.coalesce(func.sum(StripePayoutEvent.amount), 0)).where(
                StripePayoutEvent.status == "failed",
                StripePayoutEvent.failed_at.isnot(None),
                StripePayoutEvent.failed_at >= month_start,
                StripePayoutEvent.failed_at < next_month,
            )
        )
    ).scalar() or Decimal("0")

    manual_deposits = (
        await db.execute(
            select(func.coalesce(func.sum(ManualDepositEntry.amount), 0)).where(
                ManualDepositEntry.reason == "manual_bank_deposit",
                ManualDepositEntry.date >= month_start,
                ManualDepositEntry.date < next_month,
            )
        )
    ).scalar() or Decimal("0")

    manual_adjustments = (
        await db.execute(
            select(func.coalesce(func.sum(ManualDepositEntry.amount), 0)).where(
                ManualDepositEntry.reason == "adjustment",
                ManualDepositEntry.date >= month_start,
                ManualDepositEntry.date < next_month,
            )
        )
    ).scalar() or Decimal("0")

    unlinked_payment_events = (
        await db.execute(
            select(func.count(StripePaymentEvent.id)).where(
                StripePaymentEvent.unlinked == True,
                StripePaymentEvent.occurred_at >= month_start,
                StripePaymentEvent.occurred_at < next_month,
            )
        )
    ).scalar() or 0

    unlinked_payout_events = (
        await db.execute(
            select(func.count(StripePayoutEvent.id)).where(
                StripePayoutEvent.unlinked == True,
                StripePayoutEvent.created_at >= month_start,
                StripePayoutEvent.created_at < next_month,
            )
        )
    ).scalar() or 0

    net_received = (Decimal(payments_received) - Decimal(refunds)).quantize(Decimal("0.01"))
    gap_to_deposit = (net_received - Decimal(payouts_paid) - Decimal(manual_deposits)).quantize(Decimal("0.01"))

    return StripeReconciliationSummary(
        period=period_key,
        payments_received=Decimal(payments_received).quantize(Decimal("0.01")),
        refunds=Decimal(refunds).quantize(Decimal("0.01")),
        net_received=net_received,
        payouts_paid=Decimal(payouts_paid).quantize(Decimal("0.01")),
        payouts_failed=Decimal(payouts_failed).quantize(Decimal("0.01")),
        manual_deposits=Decimal(manual_deposits).quantize(Decimal("0.01")),
        manual_adjustments=Decimal(manual_adjustments).quantize(Decimal("0.01")),
        gap_to_deposit=gap_to_deposit,
        unlinked_payment_events=unlinked_payment_events,
        unlinked_payout_events=unlinked_payout_events,
    )


@router.get("/stripe/unlinked", response_model=StripeUnlinkedEventsResponse)
async def list_unlinked_stripe_events(
    period: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, month_start, next_month = _resolve_period(period)
    safe_limit = max(1, min(limit, 500))

    payment_query = (
        select(StripePaymentEvent)
        .where(
            StripePaymentEvent.unlinked == True,
            StripePaymentEvent.occurred_at >= month_start,
            StripePaymentEvent.occurred_at < next_month,
        )
        .order_by(StripePaymentEvent.occurred_at.desc())
        .limit(safe_limit)
    )
    payout_query = (
        select(StripePayoutEvent)
        .where(
            StripePayoutEvent.unlinked == True,
            StripePayoutEvent.created_at >= month_start,
            StripePayoutEvent.created_at < next_month,
        )
        .order_by(StripePayoutEvent.created_at.desc())
        .limit(safe_limit)
    )

    payment_rows = (await db.execute(payment_query)).scalars().all()
    payout_rows = (await db.execute(payout_query)).scalars().all()
    return StripeUnlinkedEventsResponse(
        payment_events=payment_rows,
        payout_events=payout_rows,
        payment_count=len(payment_rows),
        payout_count=len(payout_rows),
    )


@router.post("/stripe/unlinked/payment/{stripe_event_id}/link", response_model=StripeLinkEventResponse)
async def link_unlinked_payment_event(
    stripe_event_id: str,
    data: StripeLinkEventRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await db.execute(
        select(StripePaymentEvent).where(StripePaymentEvent.stripe_event_id == stripe_event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Stripe payment event not found")

    event.account_id = data.account_id
    event.customer_id = data.customer_id
    event.unlinked = False
    db.add(event)

    income_key = _income_key_for_payment_event(event)
    income_rows = await db.execute(
        select(IncomeEntry).where(IncomeEntry.stripe_payment_id == income_key)
    )
    incomes = income_rows.scalars().all()
    for income in incomes:
        income.account_id = data.account_id
        if data.customer_id is not None:
            income.customer_id = data.customer_id
        db.add(income)

    return StripeLinkEventResponse(
        linked=True,
        stripe_event_id=event.stripe_event_id,
        account_id=event.account_id,
        customer_id=event.customer_id,
        updated_income_rows=len(incomes),
    )


@router.post("/stripe/unlinked/payout/{stripe_event_id}/link", response_model=StripeLinkEventResponse)
async def link_unlinked_payout_event(
    stripe_event_id: str,
    data: StripeLinkEventRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await db.execute(
        select(StripePayoutEvent).where(StripePayoutEvent.stripe_event_id == stripe_event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Stripe payout event not found")

    event.account_id = data.account_id
    event.unlinked = False
    db.add(event)

    return StripeLinkEventResponse(
        linked=True,
        stripe_event_id=event.stripe_event_id,
        account_id=event.account_id,
        updated_income_rows=0,
    )


@router.get("/rollout/parity-check", response_model=FinanceParityCheckResponse)
async def rollout_parity_check(
    period: str | None = None,
    threshold_mxn: Decimal = Decimal("1.00"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    period_key, month_start, next_month = _resolve_period(period)
    rate_row = await db.execute(
        select(ExchangeRate.rate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    usd_to_mxn = Decimal(str(rate_row.scalar() or 20))

    stripe_events = (
        await db.execute(
            select(StripePaymentEvent).where(
                StripePaymentEvent.occurred_at >= month_start,
                StripePaymentEvent.occurred_at < next_month,
            )
        )
    ).scalars().all()

    lifecycle_payments_mxn = Decimal("0")
    for event in stripe_events:
        lifecycle_payments_mxn += _to_mxn(Decimal(event.amount or 0), event.currency, usd_to_mxn)
    lifecycle_payments_mxn = lifecycle_payments_mxn.quantize(Decimal("0.01"))

    incomes = (
        await db.execute(
            select(IncomeEntry).where(
                IncomeEntry.date >= month_start,
                IncomeEntry.date < next_month,
            )
        )
    ).scalars().all()
    legacy_income_mxn = Decimal("0")
    for income in incomes:
        legacy_income_mxn += _to_mxn(Decimal(income.amount or 0), income.currency, usd_to_mxn)
    legacy_income_mxn = legacy_income_mxn.quantize(Decimal("0.01"))

    difference_mxn = (lifecycle_payments_mxn - legacy_income_mxn).quantize(Decimal("0.01"))
    safe_threshold = abs(Decimal(threshold_mxn))
    return FinanceParityCheckResponse(
        period=period_key,
        lifecycle_payments_mxn=lifecycle_payments_mxn,
        legacy_income_mxn=legacy_income_mxn,
        difference_mxn=difference_mxn,
        within_threshold=abs(difference_mxn) <= safe_threshold,
    )


@router.post("/manual-deposits", response_model=ManualDepositResponse, status_code=201)
async def create_manual_deposit(
    data: ManualDepositCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reason = _normalize_manual_deposit_reason(data.reason)
    entry = ManualDepositEntry(
        account_id=data.account_id,
        amount=data.amount,
        currency=data.currency,
        date=data.date,
        reason=reason,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.get("/manual-deposits", response_model=list[ManualDepositResponse])
async def list_manual_deposits(
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ManualDepositEntry).order_by(ManualDepositEntry.date.desc(), ManualDepositEntry.created_at.desc())
    if start_date:
        q = q.where(ManualDepositEntry.date >= start_date)
    if end_date:
        q = q.where(ManualDepositEntry.date <= end_date)
    result = await db.execute(q)
    return result.scalars().all()


# ─── Invoices ─────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Invoice).order_by(Invoice.issue_date.desc())
    if status:
        q = q.where(Invoice.status == status)
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=410,
        detail="Legacy invoices are read-only. Use the SAT Facturas module.",
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=410,
        detail="Legacy invoices are read-only. Use the SAT Facturas module.",
    )


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=410,
        detail="Legacy invoices are read-only. Use the SAT Facturas module.",
    )


# ─── Cash Balance ─────────────────────────────────────────────────

@router.get("/cash-balance/current", response_model=CashBalanceResponse | None)
async def current_cash_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CashBalance).order_by(CashBalance.date.desc()).limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/cash-balance", response_model=CashBalanceResponse, status_code=201)
async def update_cash_balance(
    data: CashBalanceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate = await _get_mxn_to_usd(db)
    balance = CashBalance(
        amount=data.amount,
        currency=data.currency,
        amount_usd=_to_usd(data.amount, data.currency, rate),
        date=data.date,
        notes=data.notes,
        updated_by=user.id,
    )
    db.add(balance)
    await db.flush()
    await db.refresh(balance)
    return balance
