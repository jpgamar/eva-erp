import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import Base


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    rfc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    razon_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regimen_fiscal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fiscal_postal_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cfdi_use: Mapped[str | None] = mapped_column(String(10), nullable=True, default="G03", server_default="G03")
    person_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="operativo", server_default="operativo")
    ball_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    summary_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Cross-DB link to an Eva customer account
    eva_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    auto_match_attempted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Stripe billing
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_recipient_emails: Mapped[list | None] = mapped_column(JSONB, nullable=False, default=list, server_default="'[]'::jsonb")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["EmpresaItem"]] = relationship(
        "EmpresaItem", back_populates="empresa", cascade="all, delete-orphan", order_by="EmpresaItem.created_at.desc()"
    )
    history: Mapped[list["EmpresaHistory"]] = relationship(
        "EmpresaHistory", back_populates="empresa", cascade="all, delete-orphan", order_by="EmpresaHistory.changed_at.desc()"
    )


class EmpresaItem(Base):
    __tablename__ = "empresa_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="items")


class EmpresaHistory(Base):
    __tablename__ = "empresa_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    field_changed: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="history")
