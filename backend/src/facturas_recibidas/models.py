"""ORM model for received CFDIs (gastos)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class FacturaRecibida(Base):
    """One CFDI received from a supplier. Stored with the full XML so
    we can always reproduce the original document for an audit (CFF
    30 requires 6 years of retention).
    """

    __tablename__ = "facturas_recibidas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cfdi_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)

    # Emisor (supplier)
    issuer_rfc: Mapped[str] = mapped_column(String(13), nullable=False)
    issuer_legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_tax_system: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Receptor (us). Upload must validate this matches our RFC.
    receiver_rfc: Mapped[str] = mapped_column(String(13), nullable=False)
    receiver_legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN", server_default="MXN")
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_iva: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    tax_ieps: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    iva_retention: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    isr_retention: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    cfdi_type: Mapped[str] = mapped_column(String(2), nullable=False)
    cfdi_use: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_form: Mapped[str | None] = mapped_column(String(5), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(5), nullable=True)

    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    xml_content: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    sat_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )
    sat_last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_acreditable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    acreditacion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
