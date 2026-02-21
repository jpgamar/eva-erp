import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class KPISnapshot(Base):
    __tablename__ = "kpi_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period: Mapped[str] = mapped_column(String(7), unique=True, nullable=False)  # YYYY-MM

    # Revenue
    mrr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    mrr_currency: Mapped[str] = mapped_column(String(3), default="MXN")
    arr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    mrr_growth_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_revenue_currency: Mapped[str] = mapped_column(String(3), default="MXN")

    # Expenses
    total_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_expenses_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    net_profit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    burn_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    runway_months: Mapped[Decimal | None] = mapped_column(Numeric(8, 1), nullable=True)

    # Customers
    total_customers: Mapped[int] = mapped_column(Integer, default=0)
    new_customers: Mapped[int] = mapped_column(Integer, default=0)
    churned_customers: Mapped[int] = mapped_column(Integer, default=0)
    arpu: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    ltv: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cac: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Operational
    open_tasks: Mapped[int] = mapped_column(Integer, default=0)
    overdue_tasks: Mapped[int] = mapped_column(Integer, default=0)
    prospects_in_pipeline: Mapped[int] = mapped_column(Integer, default=0)
    prospects_won: Mapped[int] = mapped_column(Integer, default=0)

    # Extensible
    data_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
