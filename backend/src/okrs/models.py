import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import Base


class OKRPeriod(Base):
    __tablename__ = "okr_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "Q1 2026"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")  # upcoming/active/completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    objectives: Mapped[list["Objective"]] = relationship(back_populates="period", cascade="all, delete-orphan")


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("okr_periods.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="on_track")  # on_track/at_risk/behind/completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    period: Mapped["OKRPeriod"] = relationship(back_populates="objectives")
    key_results: Mapped[list["KeyResult"]] = relationship(back_populates="objective", cascade="all, delete-orphan")


class KeyResult(Base):
    __tablename__ = "key_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    objective_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("objectives.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    unit: Mapped[str] = mapped_column(String(30), default="%")
    tracking_mode: Mapped[str] = mapped_column(String(20), default="manual")  # manual/auto
    auto_metric: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    progress_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    objective: Mapped["Objective"] = relationship(back_populates="key_results")
