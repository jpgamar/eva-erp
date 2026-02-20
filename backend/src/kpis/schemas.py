import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class KPICurrentResponse(BaseModel):
    mrr: Decimal
    arr: Decimal
    mrr_growth_pct: Decimal | None
    total_revenue: Decimal
    total_expenses_mxn: Decimal
    net_profit: Decimal
    burn_rate: Decimal
    runway_months: Decimal | None
    total_customers: int
    new_customers: int
    churned_customers: int
    arpu: Decimal
    open_tasks: int
    overdue_tasks: int
    prospects_in_pipeline: int
    cash_balance_mxn: Decimal | None


class KPISnapshotResponse(BaseModel):
    id: uuid.UUID
    period: str
    mrr: Decimal
    arr: Decimal
    total_revenue: Decimal
    total_expenses_mxn: Decimal
    net_profit: Decimal
    burn_rate: Decimal
    total_customers: int
    new_customers: int
    churned_customers: int
    created_at: datetime
    model_config = {"from_attributes": True}
