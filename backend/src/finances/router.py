import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, require_admin
from src.auth.models import User
from src.common.database import get_db
from src.finances.models import CashBalance, ExchangeRate, Expense, IncomeEntry, Invoice
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
    PartnerSummary,
)

router = APIRouter(prefix="/finances", tags=["finances"])

DEFAULT_RATE = Decimal("0.05")


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


def _serialize_income(entry: IncomeEntry) -> IncomeResponse:
    recurrence_type, custom_interval_months = extract_income_recurrence(entry.metadata_json, entry.is_recurring)
    monthly_amount_usd = income_monthly_mrr_equivalent(entry.amount_usd, recurrence_type, custom_interval_months)
    return IncomeResponse(
        id=entry.id,
        source=entry.source,
        stripe_payment_id=entry.stripe_payment_id,
        customer_id=entry.customer_id,
        description=entry.description,
        amount=entry.amount,
        currency=entry.currency,
        amount_usd=entry.amount_usd,
        category=entry.category,
        date=entry.date,
        is_recurring=entry.is_recurring,
        recurrence_type=recurrence_type,
        custom_interval_months=custom_interval_months,
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
        metadata_json=build_income_metadata(None, recurrence_type, custom_interval_months),
        customer_id=data.customer_id,
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
    rate = await _get_mxn_to_usd(db)

    # Generate invoice number
    year = data.issue_date.year
    count_result = await db.execute(
        select(func.count(Invoice.id))
        .where(func.extract("year", Invoice.issue_date) == year)
    )
    count = count_result.scalar() or 0
    invoice_number = f"EVA-{year}-{str(count + 1).zfill(3)}"

    subtotal = sum(item.total for item in data.line_items)
    total = subtotal + (data.tax or Decimal("0"))
    line_items_json = [item.model_dump() for item in data.line_items]

    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        description=data.description,
        line_items_json=line_items_json,
        subtotal=subtotal,
        tax=data.tax,
        total=total,
        currency=data.currency,
        total_usd=_to_usd(total, data.currency, rate),
        status="draft",
        issue_date=data.issue_date,
        due_date=data.due_date,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)
    return invoice


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
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = data.model_dump(exclude_unset=True)

    if "line_items" in update_data and update_data["line_items"] is not None:
        items = update_data.pop("line_items")
        invoice.line_items_json = [i.model_dump() if hasattr(i, "model_dump") else i for i in items]
        invoice.subtotal = sum(Decimal(str(i.get("total", i.total) if isinstance(i, dict) else i.total)) for i in (data.line_items or []))
        invoice.total = invoice.subtotal + (invoice.tax or Decimal("0"))
        rate = await _get_mxn_to_usd(db)
        invoice.total_usd = _to_usd(invoice.total, invoice.currency, rate)

    for field, value in update_data.items():
        setattr(invoice, field, value)

    db.add(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft invoices")
    await db.delete(invoice)
    return {"message": "Invoice deleted"}


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
