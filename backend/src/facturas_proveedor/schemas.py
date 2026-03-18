from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from pydantic import BaseModel, Field


class FacturaProveedorCreate(BaseModel):
    proveedor_id: uuid.UUID
    invoice_number: str
    description: str | None = None
    subtotal: Decimal = Field(gt=0)
    tax: Decimal = Decimal("0")
    currency: str = "USD"
    exchange_rate: Decimal | None = None  # auto-fetched if not provided
    issue_date: _dt.date
    due_date: _dt.date | None = None
    notes: str | None = None


class FacturaProveedorUpdate(BaseModel):
    invoice_number: str | None = None
    description: str | None = None
    subtotal: Decimal | None = Field(default=None, gt=0)
    tax: Decimal | None = None
    currency: str | None = None
    exchange_rate: Decimal | None = None
    issue_date: _dt.date | None = None
    due_date: _dt.date | None = None
    status: str | None = None
    notes: str | None = None


class FacturaProveedorResponse(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_name: str | None = None
    invoice_number: str
    description: str | None
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    currency: str
    exchange_rate: Decimal
    base_total_mxn: Decimal
    status: str
    issue_date: _dt.date
    due_date: _dt.date | None
    paid_amount: Decimal
    remaining_amount: Decimal
    notes: str | None
    pdf_url: str | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class DiferenciaCambiariaResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    document_type: str
    document_id: uuid.UUID
    proveedor_id: uuid.UUID | None
    proveedor_name: str | None = None
    currency: str
    foreign_amount: Decimal
    original_rate: Decimal
    settlement_rate: Decimal
    gain_loss_mxn: Decimal
    period: str
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class DiferenciaCambiariaSummary(BaseModel):
    total_gain_mxn: Decimal
    total_loss_mxn: Decimal
    net_mxn: Decimal
    count: int
    by_period: dict[str, Decimal]
