from __future__ import annotations

import uuid
import datetime as _dt
from pydantic import BaseModel


class ProveedorCreate(BaseModel):
    name: str
    rfc: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    default_currency: str = "USD"
    payment_terms_days: int | None = None
    notes: str | None = None


class ProveedorUpdate(BaseModel):
    name: str | None = None
    rfc: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    default_currency: str | None = None
    payment_terms_days: int | None = None
    notes: str | None = None


class ProveedorResponse(BaseModel):
    id: uuid.UUID
    name: str
    rfc: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    bank_name: str | None
    bank_account: str | None
    default_currency: str
    payment_terms_days: int | None
    notes: str | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}
