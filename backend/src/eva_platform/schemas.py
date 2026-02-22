from __future__ import annotations

import uuid
import datetime as _dt
from pydantic import BaseModel


# ── Accounts ─────────────────────────────────────────────

class EvaAccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_user_id: str
    account_type: str
    partner_id: uuid.UUID | None
    plan_tier: str | None
    billing_interval: str | None
    subscription_status: str | None
    is_active: bool
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class EvaAccountDetailResponse(EvaAccountResponse):
    default_currency: str
    timezone: str | None
    billing_currency: str
    billing_legal_name: str | None
    billing_tax_id: str | None
    facturapi_org_api_key: str | None
    branding_logo_url: str | None
    addon_agents: int
    addon_seats: int


class EvaAccountCreateRequest(BaseModel):
    name: str
    owner_email: str
    owner_name: str = ""
    account_type: str = "COMMERCE"
    partner_id: uuid.UUID | None = None
    plan_tier: str = "STANDARD"
    billing_cycle: str = "MONTHLY"
    facturapi_org_api_key: str | None = None
    temporary_password: str | None = None


# ── Account Drafts ───────────────────────────────────────

class AccountDraftCreate(BaseModel):
    name: str
    account_type: str = "COMMERCE"
    owner_email: str
    owner_name: str = ""
    partner_id: uuid.UUID | None = None
    plan_tier: str = "STANDARD"
    billing_cycle: str = "MONTHLY"
    facturapi_org_api_key: str | None = None
    notes: str | None = None
    prospect_id: uuid.UUID | None = None


class AccountDraftUpdate(BaseModel):
    name: str | None = None
    account_type: str | None = None
    owner_email: str | None = None
    owner_name: str | None = None
    partner_id: uuid.UUID | None = None
    plan_tier: str | None = None
    billing_cycle: str | None = None
    facturapi_org_api_key: str | None = None
    notes: str | None = None


class AccountDraftResponse(BaseModel):
    id: uuid.UUID
    name: str
    account_type: str
    owner_email: str
    owner_name: str
    partner_id: uuid.UUID | None
    plan_tier: str
    billing_cycle: str
    facturapi_org_api_key: str | None
    notes: str | None
    status: str
    prospect_id: uuid.UUID | None
    provisioned_account_id: uuid.UUID | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: _dt.datetime | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


# ── Monitoring ───────────────────────────────────────────

class MonitoringOverviewResponse(BaseModel):
    open_critical: int
    open_high: int
    total_open: int
    resolved_today: int


class MonitoringIssueResponse(BaseModel):
    id: uuid.UUID
    fingerprint: str
    source: str
    category: str
    severity: str
    status: str
    title: str
    summary: str | None
    occurrences: int
    first_seen_at: _dt.datetime
    last_seen_at: _dt.datetime
    acknowledged_at: _dt.datetime | None
    resolved_at: _dt.datetime | None
    model_config = {"from_attributes": True}


class MonitoringCheckResponse(BaseModel):
    id: uuid.UUID
    check_key: str
    service: str
    target: str
    status: str
    http_status: int | None
    latency_ms: float | None
    error_message: str | None
    checked_at: _dt.datetime
    model_config = {"from_attributes": True}


# ── Partners ─────────────────────────────────────────────

class EvaPartnerResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    brand_name: str | None
    type: str
    is_active: bool
    contact_email: str | None
    deal_count: int = 0
    account_count: int = 0
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class EvaPartnerCreateRequest(BaseModel):
    name: str
    brand_name: str | None = None
    type: str = "SOLUTIONS"
    owner_email: str
    owner_name: str = ""
    contact_email: str | None = None


class EvaPartnerUpdateRequest(BaseModel):
    name: str | None = None
    brand_name: str | None = None
    type: str | None = None
    contact_email: str | None = None
    is_active: bool | None = None


class EvaPartnerDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    brand_name: str | None
    logo_url: str | None
    primary_color: str | None
    type: str
    is_active: bool
    contact_email: str | None
    custom_domain: str | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    # Stats
    deal_count: int = 0
    won_deals: int = 0
    account_count: int = 0
    # Related
    accounts: list[EvaAccountResponse] = []
    deals: list[DealResponse] = []
    model_config = {"from_attributes": True}


# ── Deals ────────────────────────────────────────────────

class DealResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID | None
    company_name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    stage: str
    plan_tier: str
    billing_cycle: str
    won_at: _dt.datetime | None
    lost_at: _dt.datetime | None
    lost_reason: str | None
    linked_account_id: uuid.UUID | None
    notes: str | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class DealCreateRequest(BaseModel):
    partner_id: uuid.UUID | None = None
    company_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    plan_tier: str = "Standard"
    billing_cycle: str = "monthly"
    notes: str | None = None


class DealUpdateRequest(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    stage: str | None = None
    plan_tier: str | None = None
    billing_cycle: str | None = None
    notes: str | None = None


class DealLostRequest(BaseModel):
    reason: str | None = None


class DealAccountCreateRequest(BaseModel):
    name: str
    owner_email: str
    plan_tier: str = "STANDARD"
    temporary_password: str | None = None


# ── Impersonation ────────────────────────────────────────

class ImpersonationResponse(BaseModel):
    magic_link_url: str
    account_id: uuid.UUID
    account_name: str


# ── Platform Dashboard ───────────────────────────────────

class PlatformDashboardResponse(BaseModel):
    active_accounts: int
    total_accounts: int
    active_partners: int
    open_issues: int
    critical_issues: int
    draft_accounts_pending: int


# Forward ref fix
EvaPartnerDetailResponse.model_rebuild()
