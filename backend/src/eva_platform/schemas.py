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
    send_setup_email: bool = True


class AccountOnboardingResponse(BaseModel):
    owner_email: str
    onboarding_link: str
    email_status: str  # sent | failed | skipped
    email_message: str | None = None


class ResendAccountOnboardingRequest(BaseModel):
    send_setup_email: bool = True


class EvaAccountProvisionResponse(BaseModel):
    account: EvaAccountDetailResponse
    onboarding: AccountOnboardingResponse


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


class AccountDraftProvisionResponse(BaseModel):
    draft: AccountDraftResponse
    account_id: uuid.UUID
    onboarding: AccountOnboardingResponse


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


class EvaBillingUsageSummary(BaseModel):
    messages_used: int
    messages_limit: int
    agents_used: int
    agents_limit: int
    seats_used: int
    seats_limit: int


class EvaBillingAddonsSummary(BaseModel):
    extra_agents: int
    extra_seats: int
    message_pack_credits: int


class EvaBillingAccountStatus(BaseModel):
    subscription_status: str | None
    plan_tier: str | None
    billing_interval: str | None
    billing_currency: str
    current_period_start: _dt.datetime | None = None
    current_period_end: _dt.datetime | None = None
    has_active_subscription: bool
    billing_subscription_cfdi_enabled: bool
    fiscal_profile_complete: bool
    retencion_required: bool
    erp_bridge_enabled_for_retention: bool
    retencion_on_file: bool
    usage: EvaBillingUsageSummary
    addons: EvaBillingAddonsSummary


class EvaBillingDocument(BaseModel):
    id: str
    document_type: str
    status: str
    status_detail: str | None = None
    email_status: str | None = None
    cfdi_uuid: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    issued_at: _dt.datetime | None = None
    created_at: _dt.datetime


class EvaBillingAdminStatusResponse(BaseModel):
    status: EvaBillingAccountStatus
    documents: list[EvaBillingDocument]


class EvaBillingCheckoutLinkRequest(BaseModel):
    plan_tier: str | None = None
    billing_interval: str | None = None
    billing_subscription_cfdi_enabled: bool | None = None


class EvaBillingCheckoutLinkResponse(BaseModel):
    checkout_url: str


class EvaBillingRetryResponse(BaseModel):
    document_id: str
    status: str


class EvaBillingResendEmailRequest(BaseModel):
    cfdi_uuid: str = Field(..., min_length=1)


class EvaBillingResendEmailResponse(BaseModel):
    status: str
    email_status: str | None = None
    cfdi_uuid: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None


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
    send_setup_email: bool = True


class DealAccountProvisionResponse(BaseModel):
    deal: DealResponse
    account_id: uuid.UUID
    onboarding: AccountOnboardingResponse


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


class OpenclawRuntimeMonitoringEventResponse(BaseModel):
    id: uuid.UUID
    source: str
    event_type: str
    severity: str
    reason_code: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    openclaw_agent_id: uuid.UUID | None = None
    runtime_host_id: uuid.UUID | None = None
    created_at: _dt.datetime


class OpenclawRuntimeOperationSnapshotResponse(BaseModel):
    id: uuid.UUID
    operation_type: str
    status: str
    updated_at: _dt.datetime
    next_retry_at: _dt.datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None


class OpenclawRuntimeMonitoringAllocationResponse(BaseModel):
    id: uuid.UUID
    openclaw_agent_id: uuid.UUID
    employee_label: str
    employee_status: str
    readiness_state: str = "preparing"
    runtime_bootstrapped: bool = False
    chat_ready: bool = False
    user_status_message: str | None = None
    state: str
    tenant_class: str
    runtime_host_id: uuid.UUID | None = None
    cpu_reservation_mcpu: int
    ram_reservation_mb: int
    restart_lock_until: _dt.datetime | None = None
    reconnect_risk: str
    queued_reason: str | None = None
    runtime_image_digest: str | None = None
    runtime_template_version: str | None = None
    runtime_release_drift: bool = False
    provisioning_completed_at: _dt.datetime | None = None
    last_manual_intervention_at: _dt.datetime | None = None
    latest_operation: OpenclawRuntimeOperationSnapshotResponse | None = None


class OpenclawRuntimeMonitoringOverviewResponse(BaseModel):
    slots_available: int
    active_hosts: int
    warning_hosts: int
    critical_hosts: int
    queue_depth: int
    locked_tenants: int
    release_parity_status: str
    release_parity: dict[str, Any] = Field(default_factory=dict)
    release_drift_count: int = 0
    readiness_drift_count: int = 0
    manual_interventions_24h: int = 0
    hosts: list[RuntimeHostResponse] = Field(default_factory=list)
    allocations: list[OpenclawRuntimeMonitoringAllocationResponse] = Field(default_factory=list)
    incidents: list[OpenclawRuntimeMonitoringEventResponse] = Field(default_factory=list)


class OpenclawRuntimeMonitoringAgentResponse(BaseModel):
    openclaw_agent_id: uuid.UUID
    employee_label: str
    employee_status: str
    readiness_state: str = "preparing"
    runtime_bootstrapped: bool = False
    chat_ready: bool = False
    user_status_message: str | None = None
    allocation_state: str
    tenant_class: str
    runtime_host_id: uuid.UUID | None = None
    runtime_host_name: str | None = None
    runtime_host_state: str | None = None
    restart_lock_until: _dt.datetime | None = None
    reconnect_risk: str
    queued_reason: str | None = None
    runtime_image_digest: str | None = None
    runtime_template_version: str | None = None
    runtime_release_drift: bool = False
    provisioning_completed_at: _dt.datetime | None = None
    last_manual_intervention_at: _dt.datetime | None = None
    latest_operation: OpenclawRuntimeOperationSnapshotResponse | None = None
    incidents: list[OpenclawRuntimeMonitoringEventResponse] = Field(default_factory=list)


class OpenclawRuntimeFleetAuditEmployeeResponse(BaseModel):
    openclaw_agent_id: uuid.UUID
    employee_label: str
    employee_status: str
    readiness_state: str = "preparing"
    runtime_bootstrapped: bool = False
    chat_ready: bool = False
    runtime_release_drift: bool = False
    db_runtime_image_digest: str | None = None
    db_runtime_template_version: str | None = None
    actual_runtime_image_ref: str | None = None
    actual_runtime_openclaw_version: str | None = None
    actual_runtime_release_drift: bool = False
    token_state: str = "unknown"
    reprovision_recommended: bool = False
    recommended_action: str | None = None
    suspected_untracked_change: bool = False
    suspected_untracked_change_reason: str | None = None
    last_manual_intervention_at: _dt.datetime | None = None
    latest_operation: OpenclawRuntimeOperationSnapshotResponse | None = None


class OpenclawRuntimeFleetAuditResponse(BaseModel):
    checked_at: _dt.datetime
    total_employees: int
    reprovision_recommended_count: int = 0
    release_drift_count: int = 0
    readiness_drift_count: int = 0
    token_drift_count: int = 0
    suspected_untracked_change_count: int = 0
    employees: list[OpenclawRuntimeFleetAuditEmployeeResponse] = Field(default_factory=list)


class OpenclawRuntimeOverviewResponse(BaseModel):
    monitoring: OpenclawRuntimeMonitoringOverviewResponse
    fleet_audit: OpenclawRuntimeFleetAuditResponse


class OpenclawRuntimeOperatorActionResponse(BaseModel):
    accepted: bool
    message: str


class OpenclawRuntimeReprovisionCampaignResponse(BaseModel):
    accepted: bool
    campaign_id: str
    queued_count: int = 0
    message: str | None = None


class OpenclawRuntimeReprovisionCampaignStatusResponse(BaseModel):
    campaign_id: str
    state: str
    checked_at: _dt.datetime
    total_employees: int = 0
    queued_count: int = 0
    provisioning_count: int = 0
    ready_count: int = 0
    error_count: int = 0
    employee_ids: list[uuid.UUID] = Field(default_factory=list)


class OpenclawRuntimeEmployeeReprovisionRequest(BaseModel):
    force: bool = True


class OpenclawRuntimeFleetReprovisionRequest(BaseModel):
    force: bool = True


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
