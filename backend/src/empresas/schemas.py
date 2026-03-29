from __future__ import annotations

import uuid
import datetime as _dt
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
    created_at: _dt.datetime
    updated_at: _dt.datetime
    items: list[EmpresaItemResponse] = []
    model_config = {"from_attributes": True}


class EmpresaListResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    status: str
    ball_on: str | None
    summary_note: str | None
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
