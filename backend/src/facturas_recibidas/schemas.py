"""Pydantic schemas for the gastos (facturas recibidas) module."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class FacturaRecibidaResponse(BaseModel):
    id: uuid.UUID
    cfdi_uuid: str
    issuer_rfc: str
    issuer_legal_name: str
    issuer_tax_system: str | None
    receiver_rfc: str
    receiver_legal_name: str | None
    issue_date: datetime
    payment_date: date | None
    currency: str
    exchange_rate: Decimal | None
    subtotal: Decimal
    tax_iva: Decimal
    tax_ieps: Decimal
    iva_retention: Decimal
    isr_retention: Decimal
    total: Decimal
    cfdi_type: str
    cfdi_use: str | None
    payment_form: str | None
    payment_method: str | None
    category: str | None
    notes: str | None
    sat_status: str
    is_acreditable: bool
    acreditacion_notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class FacturaRecibidaUpdate(BaseModel):
    category: str | None = None
    notes: str | None = None
    is_acreditable: bool | None = None
    acreditacion_notes: str | None = None
    payment_date: date | None = None


class GastosUploadResult(BaseModel):
    """Outcome of a multi-XML upload."""
    imported: int
    duplicates: int          # XMLs we already had (by cfdi_uuid)
    rejected: int            # XMLs addressed to a different RFC or malformed
    errors: list[str]        # One error per rejected file, truncated to 200 chars


class IvaAcreditableSummary(BaseModel):
    """Monthly total surfaced by the declaración page."""
    year: int
    month: int
    iva_acreditable: Decimal
    row_count: int
