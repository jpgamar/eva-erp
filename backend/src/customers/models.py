import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Fiscal info (for CFDI invoicing)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rfc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    tax_regime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fiscal_zip: Mapped[str | None] = mapped_column(String(5), nullable=True)
    default_cfdi_use: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fiscal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    plan_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)  # starter/standard/pro/custom
    mrr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    mrr_currency: Mapped[str] = mapped_column(String(3), default="MXN")
    mrr_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    arr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    billing_interval: Mapped[str | None] = mapped_column(String(20), nullable=True)  # monthly/annual
    signup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/churned/paused/trial
    churn_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    churn_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    lifetime_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    lifetime_value_currency: Mapped[str] = mapped_column(String(3), default="MXN")
    lifetime_value_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    referral_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    prospect_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # FK added later when prospects exist
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
