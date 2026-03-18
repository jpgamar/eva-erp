from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from pydantic import BaseModel, Field


class PagoProveedorCreate(BaseModel):
    proveedor_id: uuid.UUID
    tipo: str = "anticipo"  # anticipo / pago
    description: str | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "USD"
    exchange_rate: Decimal | None = None  # auto-fetched if not provided
    payment_date: _dt.date
    payment_method: str = "transferencia"
    reference: str | None = None
    notes: str | None = None


class PagoProveedorUpdate(BaseModel):
    description: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    exchange_rate: Decimal | None = None
    payment_date: _dt.date | None = None
    payment_method: str | None = None
    reference: str | None = None
    notes: str | None = None


class PagoApplyRequest(BaseModel):
    factura_proveedor_id: uuid.UUID
    amount: Decimal = Field(gt=0)


class PagoAplicacionResponse(BaseModel):
    id: uuid.UUID
    pago_id: uuid.UUID
    factura_proveedor_id: uuid.UUID
    applied_amount: Decimal
    pago_rate: Decimal
    document_rate: Decimal
    base_amount_at_pago_rate: Decimal
    base_amount_at_document_rate: Decimal
    exchange_difference_mxn: Decimal
    applied_at: _dt.datetime
    model_config = {"from_attributes": True}


class PagoProveedorResponse(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor_name: str | None = None
    tipo: str
    description: str | None
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    base_amount_mxn: Decimal
    payment_date: _dt.date
    payment_method: str
    reference: str | None
    status: str
    applied_amount: Decimal
    remaining_amount: Decimal
    notes: str | None
    applications: list[PagoAplicacionResponse] = []
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class PagoProveedorSummary(BaseModel):
    total_pendiente_usd: Decimal
    total_pendiente_mxn: Decimal
    total_aplicado_usd: Decimal
    total_aplicado_mxn: Decimal
    total_diferencia_cambiaria_mxn: Decimal
    count_pendientes: int
    count_aplicados: int
