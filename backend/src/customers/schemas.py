import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class CustomerCreate(BaseModel):
    company_name: str
    contact_name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    industry: str | None = None
    website: str | None = None
    plan_tier: str | None = None
    mrr: Decimal | None = None
    mrr_currency: str = "MXN"
    billing_interval: str | None = None
    signup_date: date | None = None
    status: str = "active"
    referral_source: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CustomerUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    industry: str | None = None
    website: str | None = None
    plan_tier: str | None = None
    mrr: Decimal | None = None
    mrr_currency: str | None = None
    billing_interval: str | None = None
    status: str | None = None
    churn_date: date | None = None
    churn_reason: str | None = None
    referral_source: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    contact_name: str
    contact_email: str | None
    contact_phone: str | None
    industry: str | None
    website: str | None
    plan_tier: str | None
    mrr: Decimal | None
    mrr_currency: str
    mrr_mxn: Decimal | None
    arr: Decimal | None
    billing_interval: str | None
    signup_date: date | None
    status: str
    churn_date: date | None
    churn_reason: str | None
    stripe_customer_id: str | None
    lifetime_value: Decimal | None
    lifetime_value_mxn: Decimal | None
    referral_source: str | None
    notes: str | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class CustomerSummary(BaseModel):
    total_customers: int
    active_customers: int
    mrr_mxn: float
    arpu_mxn: float
    churn_rate_pct: float
