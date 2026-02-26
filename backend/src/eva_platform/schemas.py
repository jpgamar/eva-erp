from __future__ import annotations

import uuid
import datetime as _dt
from typing import Any
from decimal import Decimal

from pydantic import BaseModel, Field


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
    billing_amount: Decimal | None = Field(default=None, ge=0)
    billing_currency: str = "MXN"
    is_billable: bool = True
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
    billing_amount: Decimal | None = Field(default=None, ge=0)
    billing_currency: str | None = None
    is_billable: bool | None = None
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
    billing_amount: Decimal | None
    billing_currency: str
    is_billable: bool
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


class AccountPricingResponse(BaseModel):
    account_id: uuid.UUID
    account_name: str
    account_is_active: bool
    billing_amount: Decimal | None
    billing_currency: str
    billing_interval: str
    is_billable: bool
    notes: str | None
    pricing_complete: bool
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class AccountPricingUpdateRequest(BaseModel):
    billing_amount: Decimal | None = Field(default=None, ge=0)
    billing_currency: str | None = None
    billing_interval: str | None = None
    is_billable: bool | None = None
    notes: str | None = None


class AccountPricingCoverageResponse(BaseModel):
    active_accounts: int
    billable_accounts: int
    configured_accounts: int
    missing_accounts: int
    coverage_pct: float


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
    details: dict[str, Any] | None = None
    consecutive_failures: int | None = None
    consecutive_successes: int | None = None
    last_success_at: _dt.datetime | None = None
    critical: bool | None = None
    checked_at: _dt.datetime
    model_config = {"from_attributes": True}


# ── Service Status ───────────────────────────────────────

class ServiceStatusItem(BaseModel):
    check_key: str | None = None
    name: str
    url: str
    status: str  # "up" | "down" | "degraded"
    latency_ms: int | None = None
    http_status: int | None = None
    error: str | None = None
    checked_at: _dt.datetime | None = None
    critical: bool | None = None
    consecutive_failures: int | None = None
    consecutive_successes: int | None = None
    last_success_at: _dt.datetime | None = None
    stale: bool | None = None


class ServiceStatusResponse(BaseModel):
    services: list[ServiceStatusItem]
    checked_at: _dt.datetime


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
    pricing_billable_accounts: int = 0
    pricing_configured_accounts: int = 0
    pricing_coverage_pct: float = 0.0


# ── Infrastructure ───────────────────────────────────


class RuntimeHostResponse(BaseModel):
    id: uuid.UUID
    provider_host_id: str
    name: str
    region: str
    host_class: str
    state: str
    public_ip: str | None
    vcpu: int
    ram_mb: int
    disk_gb: int
    max_tenants: int
    tenant_count: int
    saturation: float
    last_heartbeat_at: _dt.datetime | None
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class RuntimeEmployeeResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str | None = None
    label: str
    status: str
    phone_number: str | None
    allocation_state: str | None
    container_name: str | None
    gateway_port: int | None
    cpu_reservation_mcpu: int | None
    ram_reservation_mb: int | None
    reconnect_risk: str | None
    whatsapp_connected: bool
    telegram_connected: bool
    vps_ip: str | None
    model_config = {"from_attributes": True}


class RuntimeEventResponse(BaseModel):
    id: uuid.UUID
    source: str
    event_type: str
    severity: str
    reason_code: str | None
    payload: dict[str, Any]
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class RuntimeEmployeeDetailResponse(BaseModel):
    # Agent info
    id: uuid.UUID
    agent_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str | None = None
    label: str
    status: str
    status_detail: str | None
    error: str | None
    phone_number: str | None
    connections_state: dict[str, Any]
    whatsapp_connected: bool
    telegram_connected: bool
    provisioning_started_at: _dt.datetime | None
    provisioning_completed_at: _dt.datetime | None
    # Allocation info
    allocation_state: str | None
    container_name: str | None
    gateway_port: int | None
    host_name: str | None
    host_ip: str | None
    cpu_reservation_mcpu: int | None
    ram_reservation_mb: int | None
    reconnect_risk: str | None
    queued_reason: str | None
    placed_at: _dt.datetime | None
    started_at: _dt.datetime | None
    # Recent events
    recent_events: list[RuntimeEventResponse]
    model_config = {"from_attributes": True}


class DockerContainerResponse(BaseModel):
    name: str
    state: str
    status: str
    ports: str
    image: str
    created_at: str


class FileEntryResponse(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None
    modified_at: _dt.datetime | None


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    truncated: bool


class DockerLogsResponse(BaseModel):
    container_name: str
    lines: str
    tail: int


# Forward ref fix
EvaPartnerDetailResponse.model_rebuild()
