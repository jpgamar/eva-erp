import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import Base


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="identified")
    source: Mapped[str] = mapped_column(String(30), default="personal_network")
    referred_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_mrr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_mrr_currency: Mapped[str] = mapped_column(String(3), default="MXN")
    estimated_mrr_mxn: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tags: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_to_customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    interactions: Mapped[list["ProspectInteraction"]] = relationship(back_populates="prospect", cascade="all, delete-orphan")


class ProspectInteraction(Base):
    __tablename__ = "prospect_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prospect_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("prospects.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # call/email/whatsapp/meeting/demo/note
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prospect: Mapped["Prospect"] = relationship(back_populates="interactions")
