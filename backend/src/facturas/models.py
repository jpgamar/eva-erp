import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facturapi_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    cfdi_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Customer info (denormalized from Facturapi response)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_rfc: Mapped[str] = mapped_column(String(13), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    customer_tax_system: Mapped[str | None] = mapped_column(String(5), nullable=True)
    customer_zip: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # CFDI metadata
    use: Mapped[str] = mapped_column(String(10), nullable=False)  # Uso de CFDI e.g. G03
    payment_form: Mapped[str] = mapped_column(String(5), nullable=False)  # Forma de pago e.g. 28
    payment_method: Mapped[str] = mapped_column(String(5), default="PUE")  # PUE / PPD

    # Line items stored as JSON
    line_items_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    isr_retention: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    iva_retention: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # State-level retention (e.g., Guanajuato cedular 2%). Lives in the CFDI's
    # Impuestos Locales 1.0 complement, not in the federal Impuestos node.
    local_retention: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    local_retention_state: Mapped[str | None] = mapped_column(String(3), nullable=True)
    local_retention_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MXN")

    # Status — outbox lifecycle:
    #   draft          → not yet submitted for stamping (user is still editing)
    #   pending_stamp  → row committed, waiting for worker to call FacturAPI
    #   valid          → FacturAPI returned 200, CFDI signed by SAT
    #   stamp_failed   → exceeded max retries, needs human intervention
    #   cancelled      → SAT cancellation accepted
    status: Mapped[str] = mapped_column(String(20), default="draft")
    cancellation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Outbox pattern fields (see migration w2x3y4z5a6b7 for context).
    # The idempotency key is what lets us safely retry: FacturAPI returns the
    # same CFDI if we repeat the POST with the same key, so a worker crash
    # between "FacturAPI stamped" and "DB committed" cannot cause duplicates.
    facturapi_idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    stamp_retry_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    last_stamp_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stamp_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # File URLs (from Facturapi)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    xml_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dates
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    series: Mapped[str | None] = mapped_column(String(25), nullable=True)
    folio_number: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Payment tracking for PPD facturas. Running tally of payments received
    # (from ``cfdi_payments`` rows). ``payment_status`` is a cached bucket
    # derived from total_paid / total — kept on the row so list/filter
    # queries don't need to re-sum every request.
    total_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unpaid", server_default="unpaid"
    )


class CfdiPayment(Base):
    """A CFDI tipo P (Complemento de Pago) linked to a PPD factura.

    Flow: user registers a payment → row inserted as ``pending_stamp``
    → outbox worker POSTs /v2/invoices with ``type="P"`` → row
    transitions to ``valid`` with the SAT UUID. Same retry +
    idempotency machinery as ``Factura``.

    SAT rule: the complement must be emitted by the 5th calendar day
    of the month following the payment. The outbox worker orders by
    ``payment_date`` ascending so oldest (most at-risk) rows stamp first.
    """

    __tablename__ = "cfdi_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    factura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facturas.id"), nullable=False
    )
    facturapi_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    cfdi_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Payment details
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_form: Mapped[str] = mapped_column(String(5), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="MXN", server_default="MXN"
    )
    exchange_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    last_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    installment: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1"
    )

    # Outbox fields (mirror Factura's)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_stamp",
        server_default="pending_stamp",
    )
    stamp_retry_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    last_stamp_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stamp_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    facturapi_idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )

    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    xml_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
