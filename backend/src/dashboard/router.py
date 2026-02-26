"""Consolidated dashboard endpoint — one request, all queries in parallel."""

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import async_session
from src.customers.models import Customer
from src.finances.models import CashBalance, Expense, IncomeEntry
from src.finances.recurrence import (
    extract_income_recurrence,
    income_monthly_equivalent,
    income_monthly_mrr_equivalent,
)
from src.meetings.models import Meeting
from src.prospects.models import Prospect
from src.tasks.models import Task
from src.vault.models import Credential

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardResponse(BaseModel):
    period: str
    period_label: str
    is_current_period: bool
    # KPIs
    mrr: Decimal
    arr: Decimal
    total_revenue: Decimal
    total_expenses_usd: Decimal
    net_profit: Decimal
    burn_rate: Decimal
    cash_balance_usd: Decimal | None
    runway_months: Decimal | None
    total_customers: int
    new_customers: int
    churned_customers: int
    arpu: Decimal
    open_tasks: int
    overdue_tasks: int
    # Income
    income_mrr: Decimal
    income_mrr_by_currency: dict[str, Decimal]
    income_total_period: Decimal
    income_total_period_by_currency: dict[str, Decimal]
    # Expenses
    expense_total_usd: Decimal
    expense_total_period_by_currency: dict[str, Decimal]
    expense_by_category: dict[str, float]
    expense_recurring_total: Decimal
    net_profit_by_currency: dict[str, Decimal]
    # Prospects
    prospect_total: int
    prospect_by_status: dict[str, int]
    prospect_urgency: dict[str, int]
    # Tasks
    recent_tasks: list[dict]
    # Meetings
    total_meetings: int
    upcoming_meetings: int
    meetings_this_month: int
    # Vault
    vault_combined_usd: float
    vault_service_count: int
    vault_by_category: dict[str, float]


async def _run_query(query):
    """Run a single query in its own session for true parallelism."""
    async with async_session() as session:
        result = await session.execute(query)
        return result


def _next_month(value: date) -> date:
    return (value.replace(day=28) + timedelta(days=4)).replace(day=1)


def _resolve_period(period: str | None, today: date) -> tuple[str, date, date, bool]:
    if period is None:
        month_start = today.replace(day=1)
    else:
        try:
            month_start = date.fromisoformat(f"{period}-01")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid period format. Expected YYYY-MM.") from exc
    next_month_start = _next_month(month_start)
    period_key = month_start.strftime("%Y-%m")
    return period_key, month_start, next_month_start, period_key == today.strftime("%Y-%m")


@router.get("/summary", response_model=DashboardResponse)
async def dashboard_summary(
    period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user: User = Depends(get_current_user),
):
    today = date.today()
    period_key, month_start, next_month_start, is_current_period = _resolve_period(period, today)
    period_end = next_month_start - timedelta(days=1)
    period_label = month_start.strftime("%B %Y")

    active_customer_condition = and_(
        Customer.signup_date.isnot(None),
        Customer.signup_date <= period_end,
        or_(
            Customer.status == "active",
            and_(
                Customer.status == "churned",
                or_(Customer.churn_date.is_(None), Customer.churn_date > period_end),
            ),
        ),
    )

    # Define all queries upfront
    queries = {
        "mrr": select(func.coalesce(func.sum(Customer.mrr_usd), 0)).where(active_customer_condition),
        "revenue": select(func.coalesce(func.sum(IncomeEntry.amount_usd), 0)).where(
            IncomeEntry.date >= month_start,
            IncomeEntry.date < next_month_start,
        ),
        "total_expenses": select(func.coalesce(func.sum(Expense.amount_usd), 0)).where(
            Expense.date >= month_start,
            Expense.date < next_month_start,
        ),
        "burn_rate": select(func.coalesce(func.sum(Expense.amount_usd), 0)).where(
            Expense.is_recurring == True,
            Expense.date < next_month_start,
        ),
        "cash": select(CashBalance).where(CashBalance.date <= period_end).order_by(CashBalance.date.desc()).limit(1),
        "total_cust": select(func.count(Customer.id)).where(active_customer_condition),
        "new_cust": select(func.count(Customer.id)).where(
            Customer.signup_date >= month_start,
            Customer.signup_date < next_month_start,
        ),
        "churned": select(func.count(Customer.id)).where(
            Customer.status == "churned",
            Customer.churn_date.isnot(None),
            Customer.churn_date >= month_start,
            Customer.churn_date < next_month_start,
        ),
        "open_tasks": select(func.count(Task.id)).where(
            Task.status != "done",
            func.date(Task.created_at) < next_month_start,
        ),
        "overdue_tasks": select(func.count(Task.id)).where(
            Task.status != "done",
            func.date(Task.created_at) < next_month_start,
            Task.due_date.isnot(None),
            Task.due_date <= period_end,
        ),
        "all_income": select(IncomeEntry).where(IncomeEntry.date < next_month_start),
        "all_expenses": select(Expense).where(Expense.date < next_month_start),
        "all_prospects": select(Prospect).where(func.date(Prospect.created_at) < next_month_start),
        "tasks_active": select(Task).where(
            Task.status.in_(["todo", "in_progress"]),
            func.date(Task.created_at) < next_month_start,
        ).order_by(Task.created_at.desc()).limit(6),
        "total_meetings": select(func.count(Meeting.id)).where(Meeting.date < next_month_start),
        "upcoming_meetings": select(func.count(Meeting.id)).where(Meeting.date > func.now()),
        "meetings_this_month": select(func.count(Meeting.id)).where(
            Meeting.date >= month_start,
            Meeting.date < next_month_start,
        ),
        "vault_creds": select(Credential).where(
            Credential.is_deleted == False,
            Credential.monthly_cost.isnot(None),
            func.date(Credential.created_at) < next_month_start,
        ),
    }

    # Run ALL queries in parallel using separate sessions
    results = await asyncio.gather(*(
        _run_query(q) for q in queries.values()
    ))
    r = dict(zip(queries.keys(), results))

    # Extract scalars
    mrr = r["mrr"].scalar() or Decimal("0")
    total_revenue = r["revenue"].scalar() or Decimal("0")
    total_expenses_usd = r["total_expenses"].scalar() or Decimal("0")
    burn_rate = r["burn_rate"].scalar() or Decimal("0")
    cash = r["cash"].scalar_one_or_none()
    cash_balance_usd = cash.amount_usd if cash else None
    runway = Decimal(str(cash_balance_usd / burn_rate)) if cash_balance_usd and burn_rate > 0 else None
    total_cust = r["total_cust"].scalar() or 0
    new_cust = r["new_cust"].scalar() or 0
    churned = r["churned"].scalar() or 0
    arpu = Decimal(str(mrr / total_cust)) if total_cust > 0 else Decimal("0")
    open_tasks = r["open_tasks"].scalar() or 0
    overdue_tasks = r["overdue_tasks"].scalar() or 0
    total_meetings = r["total_meetings"].scalar() or 0
    upcoming_meetings = r["upcoming_meetings"].scalar() or 0
    meetings_this_month = r["meetings_this_month"].scalar() or 0

    # Income MRR supports monthly/custom/one-time recurrence from metadata.
    income_entries = r["all_income"].scalars().all()
    income_mrr = Decimal("0")
    income_mrr_by_currency: dict[str, Decimal] = {}
    income_total_period_by_currency: dict[str, Decimal] = {}
    for income in income_entries:
        recurrence_type, custom_interval_months = extract_income_recurrence(income.metadata_json, income.is_recurring)
        monthly_native = income_monthly_equivalent(income.amount, recurrence_type, custom_interval_months)
        if monthly_native > 0:
            income_mrr_by_currency[income.currency] = (
                income_mrr_by_currency.get(income.currency, Decimal("0")) + monthly_native
            ).quantize(Decimal("0.01"))

        if month_start <= income.date < next_month_start:
            income_total_period_by_currency[income.currency] = (
                income_total_period_by_currency.get(income.currency, Decimal("0")) + income.amount
            ).quantize(Decimal("0.01"))

        income_mrr += income_monthly_mrr_equivalent(income.amount_usd, recurrence_type, custom_interval_months)
    income_mrr = income_mrr.quantize(Decimal("0.01"))

    # Process expenses
    expenses = r["all_expenses"].scalars().all()
    expense_by_category: dict[str, float] = {}
    expense_recurring_total = Decimal("0")
    expense_total_period_by_currency: dict[str, Decimal] = {}
    for e in expenses:
        if e.is_recurring:
            expense_recurring_total += e.amount_usd
        if month_start <= e.date < next_month_start:
            expense_by_category[e.category] = expense_by_category.get(e.category, 0) + float(e.amount_usd)
            expense_total_period_by_currency[e.currency] = (
                expense_total_period_by_currency.get(e.currency, Decimal("0")) + e.amount
            ).quantize(Decimal("0.01"))

    net_profit_by_currency: dict[str, Decimal] = {}
    for currency in set(income_total_period_by_currency.keys()) | set(expense_total_period_by_currency.keys()):
        net_profit_by_currency[currency] = (
            income_total_period_by_currency.get(currency, Decimal("0"))
            - expense_total_period_by_currency.get(currency, Decimal("0"))
        ).quantize(Decimal("0.01"))

    # Process prospects
    prospects = r["all_prospects"].scalars().all()
    prospect_by_status: dict[str, int] = {}
    urgency = {"urgent": 0, "soso": 0, "can_wait": 0}
    for p in prospects:
        prospect_by_status[p.status] = prospect_by_status.get(p.status, 0) + 1
        tags = p.tags or []
        if "priority_high" in tags:
            urgency["urgent"] += 1
        elif "priority_medium" in tags:
            urgency["soso"] += 1
        elif "priority_low" in tags:
            urgency["can_wait"] += 1

    # Process tasks
    tasks = r["tasks_active"].scalars().all()
    recent_tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks
    ]

    # Process vault
    creds = r["vault_creds"].scalars().all()
    vault_combined_usd = sum(float(c.monthly_cost_usd or 0) for c in creds)
    vault_by_category: dict[str, float] = {}
    for c in creds:
        vault_by_category[c.category] = vault_by_category.get(c.category, 0) + float(c.monthly_cost_usd or 0)

    return DashboardResponse(
        period=period_key,
        period_label=period_label,
        is_current_period=is_current_period,
        mrr=mrr,
        arr=mrr * 12,
        total_revenue=total_revenue,
        total_expenses_usd=total_expenses_usd,
        net_profit=total_revenue - total_expenses_usd,
        burn_rate=burn_rate,
        cash_balance_usd=cash_balance_usd,
        runway_months=runway,
        total_customers=total_cust,
        new_customers=new_cust,
        churned_customers=churned,
        arpu=arpu,
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        income_mrr=income_mrr,
        income_mrr_by_currency=income_mrr_by_currency,
        income_total_period=total_revenue,
        income_total_period_by_currency=income_total_period_by_currency,
        expense_total_usd=total_expenses_usd,
        expense_total_period_by_currency=expense_total_period_by_currency,
        expense_by_category=expense_by_category,
        expense_recurring_total=expense_recurring_total,
        net_profit_by_currency=net_profit_by_currency,
        prospect_total=len(prospects),
        prospect_by_status=prospect_by_status,
        prospect_urgency=urgency,
        recent_tasks=recent_tasks,
        total_meetings=total_meetings,
        upcoming_meetings=upcoming_meetings,
        meetings_this_month=meetings_this_month,
        vault_combined_usd=vault_combined_usd,
        vault_service_count=len(creds),
        vault_by_category=vault_by_category,
    )
