"""add cfdi_payments + facturas.payment tracking for Complementos de Pago

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-04-18

When a customer invoice is emitted as PPD (pago en parcialidades o
diferido), SAT requires a separate CFDI tipo P (Complemento de Pago)
each time the customer actually pays. The ERP had zero support for
this — a gap that blocks any PPD-based B2B sale.

This migration adds:

1. ``cfdi_payments`` table — one row per payment received, outbox-style
   (status='pending_stamp' → 'valid' once FacturAPI confirms).
2. ``facturas.total_paid`` — running sum of complementos for the row.
3. ``facturas.payment_status`` — 'unpaid' / 'partial' / 'paid',
   derived from total_paid vs total.

Tests in test_payment_complements.py cover the payload structure and
the outbox integration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.first() is not None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": table},
    )
    return result.first() is not None


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": name},
        ).first()
        is not None
    )


def upgrade() -> None:
    if not _table_exists("cfdi_payments"):
        op.create_table(
            "cfdi_payments",
            sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "factura_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("facturas.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("facturapi_id", sa.String(255), nullable=True, unique=True),
            sa.Column("cfdi_uuid", sa.String(255), nullable=True),
            # The money fields
            sa.Column("payment_date", sa.Date(), nullable=False),
            sa.Column("payment_form", sa.String(5), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
            sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=True),
            sa.Column("payment_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("last_balance", sa.Numeric(12, 2), nullable=True),
            sa.Column("installment", sa.Integer(), nullable=False, server_default="1"),
            # Outbox fields mirror facturas
            sa.Column("status", sa.String(20), nullable=False, server_default="pending_stamp"),
            sa.Column("stamp_retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_stamp_error", sa.Text(), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("stamp_attempted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("facturapi_idempotency_key", sa.String(64), nullable=True),
            # CFDI file URLs
            sa.Column("pdf_url", sa.String(512), nullable=True),
            sa.Column("xml_url", sa.String(512), nullable=True),
            # Audit
            sa.Column(
                "created_by",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "ix_cfdi_payments_factura_id",
            "cfdi_payments",
            ["factura_id"],
        )
        # Unique idempotency key (outbox invariant — same payload → same CFDI)
        op.create_index(
            "uq_cfdi_payments_idempotency_key",
            "cfdi_payments",
            ["facturapi_idempotency_key"],
            unique=True,
        )
        # Worker pickup index for the same pattern the facturas outbox uses.
        op.create_index(
            "ix_cfdi_payments_outbox_pickup",
            "cfdi_payments",
            ["status", "next_retry_at"],
            postgresql_where=sa.text(
                "status IN ('pending_stamp', 'stamp_failed')"
            ),
        )
        # SAT 5-day rule: complementos must be issued by day 5 of the
        # month following the payment. Workers order by payment_date
        # ascending so oldest (most at-risk) payments stamp first.
        op.create_index(
            "ix_cfdi_payments_payment_date",
            "cfdi_payments",
            ["payment_date"],
        )

    if not _column_exists("facturas", "total_paid"):
        op.add_column(
            "facturas",
            sa.Column(
                "total_paid",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
        )
    if not _column_exists("facturas", "payment_status"):
        op.add_column(
            "facturas",
            sa.Column(
                "payment_status",
                sa.String(20),
                nullable=False,
                server_default="unpaid",
            ),
        )


def downgrade() -> None:
    if _column_exists("facturas", "payment_status"):
        op.drop_column("facturas", "payment_status")
    if _column_exists("facturas", "total_paid"):
        op.drop_column("facturas", "total_paid")
    for idx_name in (
        "ix_cfdi_payments_payment_date",
        "ix_cfdi_payments_outbox_pickup",
        "uq_cfdi_payments_idempotency_key",
        "ix_cfdi_payments_factura_id",
    ):
        if _index_exists(idx_name):
            op.drop_index(idx_name, table_name="cfdi_payments")
    if _table_exists("cfdi_payments"):
        op.drop_table("cfdi_payments")
