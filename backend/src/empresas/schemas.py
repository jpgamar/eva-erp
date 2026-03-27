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


class EmpresaItemResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    type: str
    title: str
    description: str | None
    status: str
    priority: str | None
    due_date: _dt.date | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
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
    created_at: _dt.datetime
    updated_at: _dt.datetime
    items: list[EmpresaItemResponse] = []
    model_config = {"from_attributes": True}


class EmpresaListResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    item_count: int = 0
    model_config = {"from_attributes": True}


# ── Empresa Items (Needs / Tasks) ───────────────────────────────────

class EmpresaItemCreate(BaseModel):
    type: str  # "need" or "task"
    title: str
    description: str | None = None
    status: str = "open"
    priority: str | None = None  # only for needs
    due_date: _dt.date | None = None


class EmpresaItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: _dt.date | None = None
