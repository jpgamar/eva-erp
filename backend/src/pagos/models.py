import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class PagoProveedor(Base):
    __tablename__ = "pagos_proveedor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), default="anticipo")  # anticipo / pago
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # frozen at payment date
    base_amount_mxn: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # amount * exchange_rate
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="transferencia")  # transferencia/cheque/efectivo
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)  # bank ref, check #
    status: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente/parcial/aplicado/cancelado
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PagoAplicacion(Base):
    __tablename__ = "pago_aplicaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pago_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pagos_proveedor.id"), nullable=False)
    factura_proveedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("facturas_proveedor.id"), nullable=False)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # in transaction currency
    pago_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # rate from pago
    document_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # rate from bill
    base_amount_at_pago_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    base_amount_at_document_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    exchange_difference_mxn: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # gain/loss
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
