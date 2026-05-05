import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    # Pipeline stage — Kanban source of truth; empresas.status is now secondary.
    lifecycle_stage: Mapped[str] = mapped_column(
        String(20), nullable=False, default="prospecto", server_default="prospecto"
    )
    ball_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    summary_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    billing_interval: Mapped[str] = mapped_column(
        String(10), nullable=False, default="monthly", server_default="monthly"
    )
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    constancia_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optimistic lock — incremented on every successful PATCH; clients send
    # If-Match: <version>.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Fiscal sync retry state.
    fiscal_sync_pending_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fiscal_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    grandfathered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Cross-DB link to an Eva customer account.
    eva_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    auto_match_attempted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Stripe billing.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_recipient_emails: Mapped[list | None] = mapped_column(JSONB, nullable=False, default=list, server_default="'[]'::jsonb")

    # Preserved prospect fields (merged from prospects table; see Phase 2 migration).
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    referred_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_mrr_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    estimated_mrr_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    prospect_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    tags: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    legacy_prospect_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["EmpresaItem"]] = relationship(
        "EmpresaItem", back_populates="empresa", cascade="all, delete-orphan", order_by="EmpresaItem.created_at.desc()"
    )
    history: Mapped[list["EmpresaHistory"]] = relationship(
        "EmpresaHistory", back_populates="empresa", cascade="all, delete-orphan", order_by="EmpresaHistory.changed_at.desc()"
    )
    interactions: Mapped[list["EmpresaInteraction"]] = relationship(
        "EmpresaInteraction", back_populates="empresa", cascade="all, delete-orphan", order_by="EmpresaInteraction.date.desc()"
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


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN", server_default="MXN")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, default="month")
    # Drives canonical product selection for first-time Checkout; one of
    # 'standard' or 'pro'. RENTS_* paths do not use payment_links.
    plan_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard", server_default="standard"
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    empresa: Mapped["Empresa"] = relationship("Empresa")


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


class EmpresaInteraction(Base):
    """Timeline of operator-logged interactions with an empresa.

    Merged from the former ``prospect_interactions`` table during the Phase 2
    Empresas Pipeline unification migration.
    """

    __tablename__ = "empresa_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="interactions")


class ProspectEmpresaMap(Base):
    """Traceability mapping — every prospect has exactly one empresa row.

    Created during Phase 2 migration; used by down-migration to locate the
    empresa rows inserted from prospects.
    """

    __tablename__ = "prospect_empresa_map"

    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prospects.id"), primary_key=True
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
