import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.customers.models import Customer
from src.finances.models import CashBalance, Expense, IncomeEntry
from src.kpis.models import KPISnapshot
from src.kpis.schemas import KPICurrentResponse, KPISnapshotResponse
from src.tasks.models import Task

router = APIRouter(prefix="/kpis", tags=["kpis"])


@router.get("/current", response_model=KPICurrentResponse)
async def current_kpis(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()

    # MRR from active customers
    mrr_result = await db.execute(
        select(func.coalesce(func.sum(Customer.mrr_usd), 0))
        .where(Customer.status == "active")
    )
    mrr = mrr_result.scalar() or Decimal("0")
    arr = mrr * 12

    # Total revenue this month
    rev_result = await db.execute(
        select(func.coalesce(func.sum(IncomeEntry.amount_usd), 0))
        .where(
            func.extract("year", IncomeEntry.date) == today.year,
            func.extract("month", IncomeEntry.date) == today.month,
        )
    )
    total_revenue = rev_result.scalar() or Decimal("0")

    # Total expenses
    exp_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount_usd), 0))
    )
    total_expenses_usd = exp_result.scalar() or Decimal("0")

    # Burn rate (recurring expenses)
    burn_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount_usd), 0))
        .where(Expense.is_recurring == True)
    )
    burn_rate = burn_result.scalar() or Decimal("0")

    # Cash balance
    cash_result = await db.execute(
        select(CashBalance).order_by(CashBalance.date.desc()).limit(1)
    )
    cash = cash_result.scalar_one_or_none()
    cash_balance_usd = cash.amount_usd if cash else None
    runway = Decimal(str(cash_balance_usd / burn_rate)) if cash_balance_usd and burn_rate > 0 else None

    # Customers
    total_cust = (await db.execute(select(func.count(Customer.id)).where(Customer.status == "active"))).scalar() or 0
    new_cust = (await db.execute(
        select(func.count(Customer.id))
        .where(Customer.signup_date >= today.replace(day=1))
    )).scalar() or 0
    churned = (await db.execute(
        select(func.count(Customer.id))
        .where(Customer.status == "churned", Customer.churn_date >= today.replace(day=1))
    )).scalar() or 0
    arpu = Decimal(str(mrr / total_cust)) if total_cust > 0 else Decimal("0")

    # Tasks — open = not done
    open_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.status != "done")
    )
    open_tasks = open_tasks_result.scalar() or 0

    overdue_result = await db.execute(
        select(func.count(Task.id)).where(Task.due_date < today, Task.status != "done")
    )
    overdue_tasks = overdue_result.scalar() or 0

    net_profit = total_revenue - total_expenses_usd

    return KPICurrentResponse(
        mrr=mrr,
        arr=arr,
        mrr_growth_pct=None,
        total_revenue=total_revenue,
        total_expenses_usd=total_expenses_usd,
        net_profit=net_profit,
        burn_rate=burn_rate,
        runway_months=runway,
        total_customers=total_cust,
        new_customers=new_cust,
        churned_customers=churned,
        arpu=arpu,
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        prospects_in_pipeline=0,
        cash_balance_usd=cash_balance_usd,
    )


@router.get("/history", response_model=list[KPISnapshotResponse])
async def kpi_history(
    months: int = 12,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KPISnapshot)
        .order_by(KPISnapshot.period.desc())
        .limit(months)
    )
    return result.scalars().all()


@router.post("/snapshot", response_model=KPISnapshotResponse)
async def force_snapshot(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    period = today.strftime("%Y-%m")

    # Check if snapshot exists
    existing = await db.execute(select(KPISnapshot).where(KPISnapshot.period == period))
    if existing.scalar_one_or_none():
        # Update existing
        current = await current_kpis(db=db, user=user)
        await db.execute(
            KPISnapshot.__table__.update()
            .where(KPISnapshot.period == period)
            .values(
                mrr=current.mrr, arr=current.arr,
                total_revenue=current.total_revenue,
                total_expenses_usd=current.total_expenses_usd,
                net_profit=current.net_profit,
                burn_rate=current.burn_rate,
                total_customers=current.total_customers,
                new_customers=current.new_customers,
                churned_customers=current.churned_customers,
            )
        )
        result = await db.execute(select(KPISnapshot).where(KPISnapshot.period == period))
        return result.scalar_one()

    current = await current_kpis(db=db, user=user)
    snapshot = KPISnapshot(
        period=period,
        mrr=current.mrr, arr=current.arr,
        total_revenue=current.total_revenue,
        total_expenses_usd=current.total_expenses_usd,
        net_profit=current.net_profit,
        burn_rate=current.burn_rate,
        total_customers=current.total_customers,
        new_customers=current.new_customers,
        churned_customers=current.churned_customers,
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot
