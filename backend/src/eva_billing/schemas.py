from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


PersonType = Literal["persona_fisica", "persona_moral"]
SourceType = Literal["subscription_invoice", "subscription_adjustment", "message_pack", "refund"]


class EvaBillingCustomer(BaseModel):
    legal_name: str
    tax_id: str
    tax_regime: str
    postal_code: str
    cfdi_use: str
    person_type: PersonType


class EvaBillingChargeQuote(BaseModel):
    kind: Literal["subscription", "message_pack", "subscription_change"]
    description: str
    base_subtotal_minor: int
    interval: Literal["monthly", "annual"] | None = None
    plan_tier: Literal["starter", "standard", "pro"] | None = None
    extra_agents: int = 0
    extra_seats: int = 0
    message_pack_credits: int = 0


class EvaBillingQuoteRequest(BaseModel):
    account_id: uuid.UUID
    currency: str = "MXN"
    owner_email: EmailStr
    recipient_emails: list[EmailStr] = Field(default_factory=list)
    customer: EvaBillingCustomer
    charge: EvaBillingChargeQuote


class EvaBillingDisplayLine(BaseModel):
    label: str
    amount_minor: int


class EvaBillingQuoteResponse(BaseModel):
    retention_applicable: bool
    currency: str
    base_subtotal_minor: int
    iva_minor: int
    isr_retention_minor: int
    iva_retention_minor: int
    payable_total_minor: int
    display_lines: list[EvaBillingDisplayLine]
    # State-level cedular retention (e.g., Guanajuato 2% for RESICO-PF→PM).
    # Zero/None when customer state isn't in the cedular matrix.
    cedular_retention_minor: int = 0
    cedular_state_code: str | None = None
    cedular_rate: Decimal | None = None


class EvaBillingStampSource(BaseModel):
    type: SourceType
    stripe_invoice_id: str | None = None
    stripe_payment_intent_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_customer_id: str | None = None
    stripe_charge_id: str | None = None


class EvaBillingStampCharge(BaseModel):
    currency: str = "MXN"
    description: str
    payable_total_minor: int
    base_subtotal_minor: int
    payment_form: str
    payment_method: str
    retention_applicable: bool
    # None preserves the current ZIP-derived behavior for legacy callers.
    # False is an explicit quote snapshot saying this paid charge did not
    # include state-level cedular withholding even if the fiscal ZIP is in GTO.
    cedular_retention_applicable: bool | None = None


class EvaBillingStampRequest(BaseModel):
    account_id: uuid.UUID
    owner_email: EmailStr
    recipient_emails: list[EmailStr] = Field(default_factory=list)
    idempotency_key: str
    source: EvaBillingStampSource
    customer: EvaBillingCustomer
    charge: EvaBillingStampCharge


class EvaBillingStampResponse(BaseModel):
    status: str
    factura_id: uuid.UUID
    facturapi_invoice_id: str | None = None
    cfdi_uuid: str | None
    pdf_url: str | None
    xml_url: str | None
    email_status: str | None


class EvaBillingRefundRequest(BaseModel):
    account_id: uuid.UUID
    owner_email: EmailStr
    recipient_emails: list[EmailStr] = Field(default_factory=list)
    idempotency_key: str
    stripe_invoice_id: str | None = None
    stripe_payment_intent_id: str | None = None
    stripe_charge_id: str | None = None
    refund_amount_minor: int
    original_total_minor: int
    currency: str = "MXN"


class EvaBillingStatusItem(BaseModel):
    record_id: uuid.UUID
    status: str
    factura_id: uuid.UUID | None
    cfdi_uuid: str | None
    email_status: str | None
    total: Decimal | None
    currency: str


class EvaBillingStatusResponse(BaseModel):
    account_id: uuid.UUID
    items: list[EvaBillingStatusItem]
