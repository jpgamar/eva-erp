from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, Field


class FacturaLineItem(BaseModel):
    product_key: str  # SAT clave de producto e.g. "43232408"
    description: str
    quantity: int = 1
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.16")
    isr_retention: Decimal | None = None   # e.g. 0.0125 for RESICO
    iva_retention: Decimal | None = None   # e.g. 0.106667 for 2/3 IVA
    # State-level cedular retention (e.g., Guanajuato 2%). Emitted in the
    # CFDI's SAT "Impuestos Locales 1.0" complement via Facturapi's
    # ``local_taxes`` field on the product.
    cedular_rate: Decimal | None = None
    cedular_label: str | None = None  # e.g. "Cedular GTO" — shown on CFDI PDF


class FacturaCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_rfc: str | None = None
    customer_tax_system: str | None = None  # Regimen fiscal e.g. "601"
    customer_zip: str | None = None  # Codigo postal e.g. "06600"
    use: str = "G03"  # Uso de CFDI
    payment_form: str = "28"  # Forma de pago (28 = transferencia)
    payment_method: str = "PUE"  # PUE or PPD
    line_items: list[FacturaLineItem]
    currency: str = "MXN"
    notes: str | None = None


class CfdiPaymentCreate(BaseModel):
    """Payload to register a payment against a PPD factura.

    ``factura_id`` is supplied as a path parameter; everything else is
    the content of the Complemento de Pago.
    """
    payment_date: _dt.date
    payment_form: Annotated[str, Field(min_length=2, max_length=5)]
    payment_amount: Annotated[Decimal, Field(gt=0)]
    currency: str = "MXN"
    exchange_rate: Decimal | None = None  # required if currency != MXN
    installment: int = 1
    last_balance: Decimal | None = None
    notes: str | None = None


class CfdiPaymentResponse(BaseModel):
    id: uuid.UUID
    factura_id: uuid.UUID
    facturapi_id: str | None
    cfdi_uuid: str | None
    payment_date: _dt.date
    payment_form: str
    payment_amount: Decimal
    currency: str
    exchange_rate: Decimal | None
    installment: int
    last_balance: Decimal | None
    status: str
    stamp_retry_count: int
    last_stamp_error: str | None
    next_retry_at: _dt.datetime | None
    pdf_url: str | None
    xml_url: str | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class FacturaResponse(BaseModel):
    id: uuid.UUID
    facturapi_id: str | None
    cfdi_uuid: str | None
    customer_name: str
    customer_rfc: str
    customer_id: uuid.UUID | None
    account_id: uuid.UUID | None
    customer_tax_system: str | None
    customer_zip: str | None
    use: str
    payment_form: str
    payment_method: str
    line_items_json: list | None
    subtotal: Decimal
    tax: Decimal
    isr_retention: Decimal
    iva_retention: Decimal
    # New columns default to 0/NULL in the DB. The ``| None`` tolerates
    # Python-constructed Factura instances that haven't been flushed yet
    # (ORM attrs are None until server_default kicks in on INSERT).
    local_retention: Decimal | None = None
    local_retention_state: str | None = None
    local_retention_rate: Decimal | None = None
    total: Decimal
    currency: str
    status: str
    cancellation_status: str | None
    pdf_url: str | None
    xml_url: str | None
    notes: str | None
    series: str | None
    folio_number: int | None
    issued_at: _dt.datetime | None
    cancelled_at: _dt.datetime | None
    created_at: _dt.datetime
    updated_at: _dt.datetime
    # Outbox fields (may be None on pre-migration rows)
    facturapi_idempotency_key: str | None = None
    stamp_retry_count: int = 0
    last_stamp_error: str | None = None
    next_retry_at: _dt.datetime | None = None
    stamp_attempted_at: _dt.datetime | None = None
    # Payment tracking (PPD)
    total_paid: Decimal = Decimal("0")
    payment_status: str = "unpaid"
    model_config = {"from_attributes": True}
