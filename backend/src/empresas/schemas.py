from __future__ import annotations

import re
import uuid
import datetime as _dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Empresa ──────────────────────────────────────────────────────────

# Mexican RFC structure (SAT):
#   Persona moral: 12 chars = 3 letters + YYMMDD + 3 alphanumeric homoclave
#   Persona fisica: 13 chars = 4 letters + YYMMDD + 3 alphanumeric homoclave
# Regression: F&M Accesorios (2026-04-13) was saved as `FAC2530067F3` —
# month digits "30" don't exist, so Facturapi rejected the CFDI stamp
# weeks later when their first invoice ran. Validating at input would have
# caught it immediately.
_RFC_PATTERN = re.compile(r"^([A-ZÑ&]{3,4})(\d{2})(\d{2})(\d{2})([A-Z0-9]{3})$")


def _validate_mexican_rfc(value: str) -> str:
    """Return the canonical (uppercased, stripped) RFC or raise ValueError.

    Caller should treat None / empty as "not provided" and skip this.
    """
    rfc = value.strip().upper()
    match = _RFC_PATTERN.match(rfc)
    if not match:
        raise ValueError(
            "RFC inválido: debe tener 12 caracteres (persona moral) o 13 "
            "(persona física), con fecha YYMMDD válida y homoclave alfanumérica"
        )
    _letters, _yy, mm, dd, _homoclave = match.groups()
    month, day = int(mm), int(dd)
    if not 1 <= month <= 12:
        raise ValueError(f"RFC inválido: el mes '{mm}' no es válido (debe ser 01-12)")
    if not 1 <= day <= 31:
        raise ValueError(f"RFC inválido: el día '{dd}' no es válido (debe ser 01-31)")
    return rfc


LifecycleStage = Literal[
    "prospecto", "interesado", "demo", "negociacion",
    "implementacion", "operativo", "churn_risk", "inactivo",
]
BillingIntervalLiteral = Literal["monthly", "annual"]


class EmpresaCreate(BaseModel):
    name: str
    logo_url: str | None = None
    industry: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    rfc: str | None = None
    razon_social: str | None = None
    regimen_fiscal: str | None = None
    fiscal_postal_code: str | None = None
    cfdi_use: str | None = "G03"
    person_type: str | None = None
    status: str = "operativo"
    lifecycle_stage: LifecycleStage = "prospecto"
    ball_on: str | None = None
    summary_note: str | None = None
    monthly_amount: Decimal | None = None
    billing_interval: BillingIntervalLiteral = "monthly"
    payment_day: int | None = None
    last_paid_date: _dt.date | None = None
    expected_close_date: _dt.date | None = None
    constancia_object_key: str | None = None
    # Cross-DB link to an Eva customer account. NULL = not yet linked.
    # Set via the searchable picker in the empresa edit dialog.
    eva_account_id: uuid.UUID | None = None
    # Preserved prospect fields.
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str | None = None
    source: str | None = None
    referred_by: str | None = None
    estimated_plan: str | None = None
    estimated_mrr_currency: str | None = None
    estimated_mrr_usd: Decimal | None = None
    prospect_notes: str | None = None
    next_follow_up: _dt.date | None = None
    assigned_to: uuid.UUID | None = None
    tags: list[str] | None = None
    lost_reason: str | None = None

    @field_validator("rfc")
    @classmethod
    def _check_rfc(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        return _validate_mexican_rfc(v)


class EmpresaUpdate(BaseModel):
    name: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    rfc: str | None = None
    razon_social: str | None = None
    regimen_fiscal: str | None = None
    fiscal_postal_code: str | None = None
    cfdi_use: str | None = None
    person_type: str | None = None
    status: str | None = None
    lifecycle_stage: LifecycleStage | None = None
    ball_on: str | None = None
    summary_note: str | None = None
    monthly_amount: Decimal | None = None
    billing_interval: BillingIntervalLiteral | None = None
    payment_day: int | None = None
    last_paid_date: _dt.date | None = None
    expected_close_date: _dt.date | None = None
    cancellation_scheduled_at: _dt.datetime | None = None
    constancia_object_key: str | None = None
    eva_account_id: uuid.UUID | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str | None = None
    source: str | None = None
    referred_by: str | None = None
    estimated_plan: str | None = None
    estimated_mrr_currency: str | None = None
    estimated_mrr_usd: Decimal | None = None
    prospect_notes: str | None = None
    next_follow_up: _dt.date | None = None
    assigned_to: uuid.UUID | None = None
    tags: list[str] | None = None
    lost_reason: str | None = None
    billing_recipient_emails: list[str] | None = None

    @field_validator("billing_recipient_emails")
    @classmethod
    def _normalize_billing_recipients(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                continue
            cleaned = raw.strip().lower()
            if not cleaned or cleaned in seen:
                continue
            if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
                continue
            seen.add(cleaned)
            out.append(cleaned)
        return out

    @field_validator("rfc")
    @classmethod
    def _check_rfc(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        return _validate_mexican_rfc(v)


class EmpresaItemResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    title: str
    done: bool
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class EmpresaResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    industry: str | None
    email: str | None
    phone: str | None
    address: str | None
    rfc: str | None
    razon_social: str | None
    regimen_fiscal: str | None
    fiscal_postal_code: str | None = None
    cfdi_use: str | None = None
    person_type: str | None = None
    status: str
    lifecycle_stage: str = "prospecto"
    ball_on: str | None
    summary_note: str | None
    monthly_amount: Decimal | None
    billing_interval: str = "monthly"
    payment_day: int | None
    last_paid_date: _dt.date | None
    expected_close_date: _dt.date | None = None
    cancellation_scheduled_at: _dt.datetime | None = None
    constancia_object_key: str | None = None
    version: int = 0
    fiscal_sync_pending_at: _dt.datetime | None = None
    fiscal_sync_error: str | None = None
    grandfathered: bool = False
    eva_account_id: uuid.UUID | None = None
    auto_match_attempted: bool = False
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    subscription_status: str | None = None
    current_period_end: _dt.datetime | None = None
    billing_recipient_emails: list[str] = []
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_role: str | None = None
    source: str | None = None
    referred_by: str | None = None
    estimated_plan: str | None = None
    estimated_mrr_currency: str | None = None
    estimated_mrr_usd: Decimal | None = None
    prospect_notes: str | None = None
    next_follow_up: _dt.date | None = None
    assigned_to: uuid.UUID | None = None
    tags: list[str] | None = None
    lost_reason: str | None = None
    legacy_prospect_id: uuid.UUID | None = None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    items: list[EmpresaItemResponse] = []
    model_config = {"from_attributes": True}


# ── Channel health (silent-channel-health plan) ──────────────────────

class ChannelTypeHealth(BaseModel):
    """Per-channel-type health for one Empresa's linked Eva account.

    ``present`` indicates whether the linked account has at least one
    active channel of this type. ``healthy`` is True only if ALL active
    channels of this type pass the worker health check.
    """

    present: bool = False
    healthy: bool = False
    count: int = 0


class EmpresaHealth(BaseModel):
    """Aggregate channel health for one Empresa.

    Returned as the ``health`` field on each Empresa list item so the
    frontend can render per-card health info without making a follow-up
    request per empresa.

    Plan: docs/archive/plans/silent-channel-health.md
    """

    status: Literal["healthy", "unhealthy", "unknown", "not_linked"]
    unhealthy_count: int = 0
    # Resolved name of the linked Eva account, or None when the empresa
    # is not linked. Surfaced on the frontend card so users can see
    # WHICH Eva customer the empresa points at without opening the
    # edit modal.
    linked_account_name: str | None = None
    # Per-channel-type breakdown so the frontend can render
    # "Messenger ✅ Instagram ❌ WhatsApp ✅" badges directly on the card.
    # ``count`` lets the badge show "Instagram · 2" when one Eva account
    # has multiple channels of the same type.
    messenger: ChannelTypeHealth = ChannelTypeHealth()
    instagram: ChannelTypeHealth = ChannelTypeHealth()
    whatsapp: ChannelTypeHealth = ChannelTypeHealth()


class ChannelHealthEntry(BaseModel):
    """One channel row inside the per-account health endpoint response."""

    id: uuid.UUID
    channel_type: Literal["messenger", "instagram", "whatsapp"]
    display_name: str | None
    is_healthy: bool
    health_status_reason: str | None
    last_status_check: _dt.datetime | None


class AccountChannelHealthResponse(BaseModel):
    """Full per-account channel health, used by the modal in Eva ERP."""

    account_id: uuid.UUID
    messenger: list[ChannelHealthEntry]
    instagram: list[ChannelHealthEntry]
    whatsapp: list[ChannelHealthEntry] = []


class EvaAccountForLink(BaseModel):
    """One row in the dropdown that links an Empresa to an Eva account."""

    id: uuid.UUID
    name: str


class EmpresaListResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    status: str
    lifecycle_stage: str = "prospecto"
    ball_on: str | None
    summary_note: str | None
    monthly_amount: Decimal | None
    billing_interval: str = "monthly"
    payment_day: int | None
    last_paid_date: _dt.date | None
    expected_close_date: _dt.date | None = None
    cancellation_scheduled_at: _dt.datetime | None = None
    subscription_status: str | None = None
    current_period_end: _dt.datetime | None = None
    eva_account_id: uuid.UUID | None = None
    grandfathered: bool = False
    version: int = 0
    item_count: int = 0
    model_config = {"from_attributes": True}


class EmpresaInteractionResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    type: str
    summary: str
    date: _dt.date
    created_by: uuid.UUID
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class EmpresaInteractionCreate(BaseModel):
    type: str
    summary: str
    date: _dt.date


# ── Empresa Items ────────────────────────────────────────────────────

class EmpresaItemCreate(BaseModel):
    title: str


class EmpresaItemUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


# ── History ──────────────────────────────────────────────────────────

class EmpresaHistoryResponse(BaseModel):
    id: uuid.UUID
    field_changed: str
    old_value: str | None
    new_value: str | None
    changed_by: uuid.UUID | None
    changed_by_name: str | None = None
    changed_at: _dt.datetime
    model_config = {"from_attributes": True}


# ── Billing / Checkout ──────────────────────────────────────────────

class PreviewCheckoutRequest(BaseModel):
    amount_mxn: Decimal = Field(..., gt=0, description="Base amount in MXN before IVA (e.g., 2000.00)")


class PreviewCheckoutResponse(BaseModel):
    retention_applicable: bool
    base_subtotal_minor: int
    iva_minor: int
    isr_retention_minor: int
    iva_retention_minor: int
    payable_total_minor: int
    stripe_charges_tax: bool


class CheckoutLinkRequest(BaseModel):
    amount_mxn: Decimal = Field(..., gt=0, description="Base amount in MXN before IVA (e.g., 2000.00)")
    description: str = Field(default="", max_length=500)
    interval: Literal["month", "year"] = "month"
    recipient_email: EmailStr
    # Drives canonical Stripe Product selection in first-time Checkout.
    plan_tier: Literal["standard", "pro"] = "standard"


class CheckoutLinkResponse(BaseModel):
    checkout_url: str
    quote: PreviewCheckoutResponse


# ── Phase 4: subscription proxy endpoints ────────────────────────────


class SubscriptionApplyRequest(BaseModel):
    plan_tier: Literal["standard", "pro"]
    billing_interval: Literal["monthly", "annual"]
    base_subtotal_minor: int = Field(..., ge=1, le=10_000_000)
    erp_description: str | None = Field(default=None, max_length=500)
    proration_behavior: Literal["always_invoice", "create_prorations", "none"] = "always_invoice"


class SubscriptionApplyResponse(BaseModel):
    subscription_id: str | None = None
    price_id: str | None = None
    product_id: str | None = None
    base_subtotal_minor: int
    payable_total_minor: int
    retention_applicable: bool
    person_type: str | None = None
    current_period_end: int | None = None
    preview: dict | None = None


class SubscriptionCancelRequest(BaseModel):
    at_period_end: bool = True
    cancel_reason: str | None = Field(default=None, max_length=500)


class SubscriptionCancelResponse(BaseModel):
    subscription_id: str
    cancel_at_period_end: bool
    cancellation_scheduled_at: int | None = None
    subscription_status: str


class PortalLinkResponse(BaseModel):
    portal_url: str


class PaymentLinkPublicResponse(BaseModel):
    empresa_name: str
    description: str
    amount_minor: int
    currency: str
    interval: str
    retention_applicable: bool
    status: str
    quote: PreviewCheckoutResponse


# ── Constancia Extraction ───────────────────────────────────────────

class ConstanciaExtractedFields(BaseModel):
    rfc: str | None = None
    legal_name: str | None = None
    tax_regime: str | None = None
    postal_code: str | None = None
    person_type: str | None = None


class ConstanciaExtractResponse(BaseModel):
    extracted: ConstanciaExtractedFields = Field(default_factory=ConstanciaExtractedFields)
    warnings: list[str] = Field(default_factory=list)
    source: str = "unknown"
