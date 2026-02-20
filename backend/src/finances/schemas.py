import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


# Exchange Rate
class ExchangeRateResponse(BaseModel):
    id: uuid.UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    source: str
    model_config = {"from_attributes": True}


class ExchangeRateUpdate(BaseModel):
    rate: Decimal
    effective_date: date | None = None


# Income
class IncomeCreate(BaseModel):
    description: str
    amount: Decimal
    currency: str = "MXN"
    category: str = "subscription"
    date: date
    is_recurring: bool = False
    customer_id: uuid.UUID | None = None


class IncomeUpdate(BaseModel):
    description: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    category: str | None = None
    date: date | None = None
    is_recurring: bool | None = None


class IncomeResponse(BaseModel):
    id: uuid.UUID
    source: str
    stripe_payment_id: str | None
    customer_id: uuid.UUID | None
    description: str
    amount: Decimal
    currency: str
    amount_mxn: Decimal
    category: str
    date: date
    is_recurring: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class IncomeSummary(BaseModel):
    mrr: Decimal
    arr: Decimal
    total_period: Decimal
    total_period_mxn: Decimal
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
    date: date
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
    date: date | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    amount: Decimal
    currency: str
    amount_mxn: Decimal
    category: str
    vendor: str | None
    paid_by: uuid.UUID
    is_recurring: bool
    recurrence: str | None
    date: date
    receipt_url: str | None
    vault_credential_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ExpenseSummary(BaseModel):
    total_mxn: Decimal
    by_category: dict[str, float]
    by_person: dict[str, float]
    recurring_total_mxn: Decimal


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
    issue_date: date
    due_date: date
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    customer_name: str | None = None
    customer_email: str | None = None
    description: str | None = None
    line_items: list[LineItem] | None = None
    tax: Decimal | None = None
    status: str | None = None
    paid_date: date | None = None
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
    total_mxn: Decimal
    status: str
    issue_date: date
    due_date: date
    paid_date: date | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# Cash Balance
class CashBalanceCreate(BaseModel):
    amount: Decimal
    currency: str = "MXN"
    date: date
    notes: str | None = None


class CashBalanceResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: str
    amount_mxn: Decimal
    date: date
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
