import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facturapi_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    cfdi_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Customer info (denormalized from Facturapi response)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_rfc: Mapped[str] = mapped_column(String(13), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)

    # CFDI metadata
    use: Mapped[str] = mapped_column(String(10), nullable=False)  # Uso de CFDI e.g. G03
    payment_form: Mapped[str] = mapped_column(String(5), nullable=False)  # Forma de pago e.g. 28
    payment_method: Mapped[str] = mapped_column(String(5), default="PUE")  # PUE / PPD

    # Line items stored as JSON
    line_items_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MXN")

    # Status
    status: Mapped[str] = mapped_column(String(20), default="valid")  # valid / cancelled
    cancellation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # File URLs (from Facturapi)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    xml_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Dates
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    series: Mapped[str | None] = mapped_column(String(25), nullable=True)
    folio_number: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
