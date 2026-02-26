from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from pydantic import BaseModel


class FacturaLineItem(BaseModel):
    product_key: str  # SAT clave de producto e.g. "43232408"
    description: str
    quantity: int = 1
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.16")
    isr_retention: Decimal | None = None   # e.g. 0.0125 for RESICO
    iva_retention: Decimal | None = None   # e.g. 0.106667 for 2/3 IVA


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
    model_config = {"from_attributes": True}
