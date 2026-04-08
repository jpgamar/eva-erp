from __future__ import annotations

import uuid
import datetime as _dt
from typing import Literal
from pydantic import BaseModel


# ── Empresa ──────────────────────────────────────────────────────────

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
    status: str = "operativo"
    ball_on: str | None = None
    summary_note: str | None = None
    monthly_amount: float | None = None
    payment_day: int | None = None
    last_paid_date: _dt.date | None = None
    # Cross-DB link to an Eva customer account. NULL = not yet linked.
    # Set automatically by the auto-match-by-name routine, or
    # manually via the Empresa edit modal.
    eva_account_id: uuid.UUID | None = None


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
    status: str | None = None
    ball_on: str | None = None
    summary_note: str | None = None
    monthly_amount: float | None = None
    payment_day: int | None = None
    last_paid_date: _dt.date | None = None
    eva_account_id: uuid.UUID | None = None


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
    status: str
    ball_on: str | None
    summary_note: str | None
    monthly_amount: float | None
    payment_day: int | None
    last_paid_date: _dt.date | None
    eva_account_id: uuid.UUID | None = None
    auto_match_attempted: bool = False
    created_at: _dt.datetime
    updated_at: _dt.datetime
    items: list[EmpresaItemResponse] = []
    model_config = {"from_attributes": True}


# ── Channel health (silent-channel-health plan) ──────────────────────

class EmpresaHealth(BaseModel):
    """Aggregate channel health for one Empresa.

    Returned as the ``health`` field on each Empresa list item so the
    frontend can render a status dot per card without making a
    follow-up request per empresa.

    Plan: docs/domains/integrations/instagram/plan-silent-channel-health.md
    """

    status: Literal["healthy", "unhealthy", "unknown", "not_linked"]
    unhealthy_count: int = 0


class ChannelHealthEntry(BaseModel):
    """One channel row inside the per-account health endpoint response."""

    id: uuid.UUID
    channel_type: Literal["messenger", "instagram"]
    display_name: str | None
    is_healthy: bool
    health_status_reason: str | None
    last_status_check: _dt.datetime | None


class AccountChannelHealthResponse(BaseModel):
    """Full per-account channel health, used by the modal in Eva ERP."""

    account_id: uuid.UUID
    messenger: list[ChannelHealthEntry]
    instagram: list[ChannelHealthEntry]


class EvaAccountForLink(BaseModel):
    """One row in the dropdown that links an Empresa to an Eva account."""

    id: uuid.UUID
    name: str


class EmpresaListResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    status: str
    ball_on: str | None
    summary_note: str | None
    monthly_amount: float | None
    payment_day: int | None
    last_paid_date: _dt.date | None
    item_count: int = 0
    model_config = {"from_attributes": True}


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
