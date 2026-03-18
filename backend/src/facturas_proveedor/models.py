import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class FacturaProveedor(Base):
    __tablename__ = "facturas_proveedor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # frozen at issue date
    base_total_mxn: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # total * exchange_rate
    status: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente/parcial/pagada/cancelada
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiferenciaCambiaria(Base):
    __tablename__ = "diferencias_cambiarias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # anticipo_application / payment
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # factura_proveedor
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    foreign_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    original_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    settlement_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gain_loss_mxn: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # positive=gain, negative=loss
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # '2026-03'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
