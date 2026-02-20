import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class ProspectCreate(BaseModel):
    company_name: str
    contact_name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str | None = None
    website: str | None = None
    industry: str | None = None
    status: str = "identified"
    source: str = "personal_network"
    referred_by: str | None = None
    estimated_plan: str | None = None
    estimated_mrr: Decimal | None = None
    estimated_mrr_currency: str = "MXN"
    notes: str | None = None
    next_follow_up: date | None = None
    assigned_to: uuid.UUID | None = None
    tags: list[str] | None = None


class ProspectUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str | None = None
    website: str | None = None
    industry: str | None = None
    status: str | None = None
    source: str | None = None
    referred_by: str | None = None
    estimated_plan: str | None = None
    estimated_mrr: Decimal | None = None
    notes: str | None = None
    next_follow_up: date | None = None
    assigned_to: uuid.UUID | None = None
    tags: list[str] | None = None
    lost_reason: str | None = None


class ProspectResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    contact_name: str
    contact_email: str | None
    contact_phone: str | None
    contact_role: str | None
    website: str | None
    industry: str | None
    status: str
    source: str
    referred_by: str | None
    estimated_plan: str | None
    estimated_mrr: Decimal | None
    estimated_mrr_currency: str
    estimated_mrr_mxn: Decimal | None
    notes: str | None
    next_follow_up: date | None
    assigned_to: uuid.UUID | None
    tags: list[str] | None
    lost_reason: str | None
    converted_to_customer_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class InteractionCreate(BaseModel):
    type: str
    summary: str
    date: date


class InteractionResponse(BaseModel):
    id: uuid.UUID
    prospect_id: uuid.UUID
    type: str
    summary: str
    date: date
    created_by: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ProspectSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    total_estimated_pipeline_mxn: float
