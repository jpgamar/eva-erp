"""Consolidated dashboard endpoint — one request, all queries in parallel."""

import asyncio
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import async_session
from src.customers.models import Customer
from src.finances.models import CashBalance, Expense, IncomeEntry
from src.prospects.models import Prospect
from src.tasks.models import Task
from src.vault.models import Credential

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardResponse(BaseModel):
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
    income_total_period: Decimal
    # Expenses
    expense_total_usd: Decimal
    expense_by_category: dict[str, float]
    expense_recurring_total: Decimal
    # Prospects
    prospect_total: int
    prospect_by_status: dict[str, int]
    prospect_urgency: dict[str, int]
    # Tasks
    recent_tasks: list[dict]
    # Vault
    vault_combined_usd: float
    vault_service_count: int
    vault_by_category: dict[str, float]


async def _run_query(query):
    """Run a single query in its own session for true parallelism."""
    async with async_session() as session:
        result = await session.execute(query)
        return result


@router.get("/summary", response_model=DashboardResponse)
async def dashboard_summary(
    user: User = Depends(get_current_user),
):
    today = date.today()
    month_start = today.replace(day=1)

    # Define all queries upfront
    queries = {
        "mrr": select(func.coalesce(func.sum(Customer.mrr_usd), 0)).where(Customer.status == "active"),
        "revenue": select(func.coalesce(func.sum(IncomeEntry.amount_usd), 0)).where(
            func.extract("year", IncomeEntry.date) == today.year,
            func.extract("month", IncomeEntry.date) == today.month,
        ),
        "total_expenses": select(func.coalesce(func.sum(Expense.amount_usd), 0)),
        "burn_rate": select(func.coalesce(func.sum(Expense.amount_usd), 0)).where(Expense.is_recurring == True),
        "cash": select(CashBalance).order_by(CashBalance.date.desc()).limit(1),
        "total_cust": select(func.count(Customer.id)).where(Customer.status == "active"),
        "new_cust": select(func.count(Customer.id)).where(Customer.signup_date >= month_start),
        "churned": select(func.count(Customer.id)).where(Customer.status == "churned", Customer.churn_date >= month_start),
        "open_tasks": select(func.count(Task.id)).where(Task.status != "done"),
        "overdue_tasks": select(func.count(Task.id)).where(Task.due_date < today, Task.status != "done"),
        "income_mrr": select(func.coalesce(func.sum(IncomeEntry.amount_usd), 0)).where(IncomeEntry.is_recurring == True),
        "all_expenses": select(Expense),
        "all_prospects": select(Prospect),
        "tasks_active": select(Task).where(Task.status.in_(["todo", "in_progress"])).order_by(Task.created_at.desc()).limit(6),
        "vault_creds": select(Credential).where(Credential.is_deleted == False, Credential.monthly_cost.isnot(None)),
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
    income_mrr = r["income_mrr"].scalar() or Decimal("0")

    # Process expenses
    expenses = r["all_expenses"].scalars().all()
    expense_by_category: dict[str, float] = {}
    expense_recurring_total = Decimal("0")
    for e in expenses:
        expense_by_category[e.category] = expense_by_category.get(e.category, 0) + float(e.amount_usd)
        if e.is_recurring:
            expense_recurring_total += e.amount_usd

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
        income_total_period=total_revenue,
        expense_total_usd=Decimal(str(sum(float(e.amount_usd) for e in expenses))),
        expense_by_category=expense_by_category,
        expense_recurring_total=expense_recurring_total,
        prospect_total=len(prospects),
        prospect_by_status=prospect_by_status,
        prospect_urgency=urgency,
        recent_tasks=recent_tasks,
        vault_combined_usd=vault_combined_usd,
        vault_service_count=len(creds),
        vault_by_category=vault_by_category,
    )
