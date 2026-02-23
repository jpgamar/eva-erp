from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# Exchange Rate
class ExchangeRateResponse(BaseModel):
    id: uuid.UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: _dt.date
    source: str
    model_config = {"from_attributes": True}


class ExchangeRateUpdate(BaseModel):
    rate: Decimal
    effective_date: _dt.date | None = None


# Income
IncomeRecurrenceType = Literal["monthly", "one_time", "custom"]


class IncomeCreate(BaseModel):
    description: str
    amount: Decimal
    currency: str = "MXN"
    category: str = "subscription"
    date: _dt.date
    recurrence_type: IncomeRecurrenceType = "one_time"
    custom_interval_months: int | None = Field(default=None, ge=1)
    # Legacy flag kept for backwards compatibility with old clients.
    is_recurring: bool = False
    customer_id: uuid.UUID | None = None


class IncomeUpdate(BaseModel):
    description: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    date: _dt.date | None = None
    recurrence_type: IncomeRecurrenceType | None = None
    custom_interval_months: int | None = Field(default=None, ge=1)
    is_recurring: bool | None = None


class IncomeResponse(BaseModel):
    id: uuid.UUID
    source: str
    stripe_payment_id: str | None
    customer_id: uuid.UUID | None
    description: str
    amount: Decimal
    currency: str
    amount_usd: Decimal
    category: str
    date: _dt.date
    is_recurring: bool
    recurrence_type: IncomeRecurrenceType
    custom_interval_months: int | None
    monthly_amount_usd: Decimal
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class IncomeSummary(BaseModel):
    mrr: Decimal
    arr: Decimal
    total_period: Decimal
    total_period_usd: Decimal
    mrr_by_currency: dict[str, Decimal]
    arr_by_currency: dict[str, Decimal]
    total_period_by_currency: dict[str, Decimal]
    mom_growth_pct: Decimal | None


# Expense
class ExpenseCreate(BaseModel):
    name: str
    description: str | None = None
    amount: Decimal
    currency: str = "USD"
    category: str
    vendor: str | None = None
    paid_by: uuid.UUID
    is_recurring: bool = False
    recurrence: str | None = None
    date: _dt.date
    vault_credential_id: uuid.UUID | None = None


class ExpenseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    vendor: str | None = None
    paid_by: uuid.UUID | None = None
    is_recurring: bool | None = None
    recurrence: str | None = None
    date: _dt.date | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    amount: Decimal
    currency: str
    amount_usd: Decimal
    category: str
    vendor: str | None
    paid_by: uuid.UUID
    is_recurring: bool
    recurrence: str | None
    date: _dt.date
    receipt_url: str | None
    vault_credential_id: uuid.UUID | None
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class ExpenseSummary(BaseModel):
    total_usd: Decimal
    by_category: dict[str, float]
    by_person: dict[str, float]
    recurring_total_usd: Decimal


class PartnerSummary(BaseModel):
    partner_totals: dict[str, float]


# Invoice
class LineItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: Decimal
    total: Decimal


class InvoiceCreate(BaseModel):
    customer_name: str
    customer_email: str | None = None
    customer_id: uuid.UUID | None = None
    description: str | None = None
    line_items: list[LineItem]
    tax: Decimal | None = None
    currency: str = "MXN"
    issue_date: _dt.date
    due_date: _dt.date
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    customer_name: str | None = None
    customer_email: str | None = None
    description: str | None = None
    line_items: list[LineItem] | None = None
    tax: Decimal | None = None
    status: str | None = None
    paid_date: _dt.date | None = None
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID | None
    customer_name: str
    customer_email: str | None
    description: str | None
    line_items_json: list | None
    subtotal: Decimal
    tax: Decimal | None
    total: Decimal
    currency: str
    total_usd: Decimal
    status: str
    issue_date: _dt.date
    due_date: _dt.date
    paid_date: _dt.date | None
    notes: str | None
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


# Cash Balance
class CashBalanceCreate(BaseModel):
    amount: Decimal
    currency: str = "MXN"
    date: _dt.date
    notes: str | None = None


class CashBalanceResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: str
    amount_usd: Decimal
    date: _dt.date
    notes: str | None
    created_at: _dt.datetime
    model_config = {"from_attributes": True}
