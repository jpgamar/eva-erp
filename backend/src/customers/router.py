import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.customers.models import Customer
from src.customers.schemas import CustomerCreate, CustomerResponse, CustomerSummary, CustomerUpdate
from src.finances.models import IncomeEntry

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    status: str | None = None,
    plan: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Customer).order_by(Customer.company_name)
    if status:
        q = q.where(Customer.status == status)
    if plan:
        q = q.where(Customer.plan_tier == plan)
    if search:
        q = q.where(Customer.company_name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mrr_mxn = None
    if data.mrr is not None:
        # Simple conversion
        from src.finances.router import _get_usd_to_mxn, _to_mxn
        rate = await _get_usd_to_mxn(db)
        mrr_mxn = _to_mxn(data.mrr, data.mrr_currency, rate)

    customer = Customer(
        company_name=data.company_name,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        industry=data.industry,
        website=data.website,
        plan_tier=data.plan_tier,
        mrr=data.mrr,
        mrr_currency=data.mrr_currency,
        mrr_mxn=mrr_mxn,
        arr=data.mrr * 12 if data.mrr else None,
        billing_interval=data.billing_interval,
        signup_date=data.signup_date,
        status=data.status,
        referral_source=data.referral_source,
        notes=data.notes,
        tags=data.tags,
        created_by=user.id,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


@router.get("/summary", response_model=CustomerSummary)
async def customer_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = await db.execute(select(func.count(Customer.id)))
    active = await db.execute(select(func.count(Customer.id)).where(Customer.status == "active"))
    mrr_result = await db.execute(
        select(func.coalesce(func.sum(Customer.mrr_mxn), 0))
        .where(Customer.status == "active")
    )

    total_count = total.scalar() or 0
    active_count = active.scalar() or 0
    mrr_mxn = float(mrr_result.scalar() or 0)
    arpu = mrr_mxn / active_count if active_count > 0 else 0

    # Churn rate: churned in last 90 days / total at start
    churned = await db.execute(
        select(func.count(Customer.id)).where(
            Customer.status == "churned",
            Customer.churn_date >= func.current_date() - 90,
        )
    )
    churned_count = churned.scalar() or 0
    churn_rate = (churned_count / total_count * 100) if total_count > 0 else 0

    return CustomerSummary(
        total_customers=total_count,
        active_customers=active_count,
        mrr_mxn=mrr_mxn,
        arpu_mxn=arpu,
        churn_rate_pct=churn_rate,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)

    # Recalculate MXN if mrr changed
    if customer.mrr is not None:
        from src.finances.router import _get_usd_to_mxn, _to_mxn
        rate = await _get_usd_to_mxn(db)
        customer.mrr_mxn = _to_mxn(customer.mrr, customer.mrr_currency, rate)
        customer.arr = customer.mrr * 12

    db.add(customer)
    return customer


@router.get("/{customer_id}/payments")
async def customer_payments(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IncomeEntry)
        .where(IncomeEntry.customer_id == customer_id)
        .order_by(IncomeEntry.date.desc())
    )
    return result.scalars().all()
