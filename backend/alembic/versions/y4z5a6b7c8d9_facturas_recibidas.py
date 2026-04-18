"""add facturas_recibidas for received CFDI tracking + IVA acreditable

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-04-18

RESICO Personas Físicas don't get ISR deductions, but they DO get
IVA acreditable on gastos with a valid CFDI to their RFC that was
effectively paid in the month. Before this migration the ERP had no
way to track received invoices, so every monthly declaration was
computed with IVA acreditable = $0 — overpaying IVA consistently.

This migration creates the storage. Phase E's declaración calculator
will aggregate ``facturas_recibidas`` by ``payment_date`` to sum the
IVA acreditable for each period.

XML is stored in full so an audit (6 years per CFF 30) can produce
the original document without round-tripping to the supplier.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y4z5a6b7c8d9"
down_revision: Union[str, None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
            ),
            {"t": table},
        ).first()
        is not None
    )


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
    if _table_exists("facturas_recibidas"):
        return
    op.create_table(
        "facturas_recibidas",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        # Deduplication key: SAT-assigned UUID is unique across every CFDI in
        # the country. Any second import of the same XML is a no-op.
        sa.Column("cfdi_uuid", sa.String(36), nullable=False, unique=True),
        # Supplier (emisor) — who billed us.
        sa.Column("issuer_rfc", sa.String(13), nullable=False),
        sa.Column("issuer_legal_name", sa.String(255), nullable=False),
        sa.Column("issuer_tax_system", sa.String(5), nullable=True),
        # Us (receptor). Validating this = our RFC is how we reject XMLs
        # that were addressed to someone else (operator mistake).
        sa.Column("receiver_rfc", sa.String(13), nullable=False),
        sa.Column("receiver_legal_name", sa.String(255), nullable=True),
        # Dates: issue_date is on the CFDI, payment_date is when we paid
        # (= when IVA becomes acreditable under flujo de efectivo).
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        # Money (mirrors CFDI fields 1:1)
        sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
        sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_iva", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_ieps", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("iva_retention", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("isr_retention", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        # CFDI metadata
        sa.Column("cfdi_type", sa.String(2), nullable=False),  # I, E, P, N, T
        sa.Column("cfdi_use", sa.String(10), nullable=True),
        sa.Column("payment_form", sa.String(5), nullable=True),
        sa.Column("payment_method", sa.String(5), nullable=True),  # PUE, PPD
        # Categorization (by operator, used in dashboards + declaración)
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Raw XML for audits. Stored in DB rather than object storage
        # because volumes are tiny (~10-50 KB per row, <100/month).
        sa.Column("xml_content", sa.Text(), nullable=False),
        sa.Column("pdf_storage_key", sa.String(512), nullable=True),
        # SAT validation (optional future feature)
        sa.Column("sat_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("sat_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        # Operator override: can flag a row as non-acreditable when the
        # gasto isn't strictly business (mixed personal/business card, etc.)
        sa.Column("is_acreditable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("acreditacion_notes", sa.Text(), nullable=True),
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
    # Declaración groups by month of payment_date, so this is the hot path.
    op.create_index("ix_facturas_recibidas_payment_date", "facturas_recibidas", ["payment_date"])
    op.create_index("ix_facturas_recibidas_issue_date", "facturas_recibidas", ["issue_date"])
    op.create_index("ix_facturas_recibidas_issuer_rfc", "facturas_recibidas", ["issuer_rfc"])
    op.create_index("ix_facturas_recibidas_category", "facturas_recibidas", ["category"])


def downgrade() -> None:
    for idx in (
        "ix_facturas_recibidas_category",
        "ix_facturas_recibidas_issuer_rfc",
        "ix_facturas_recibidas_issue_date",
        "ix_facturas_recibidas_payment_date",
    ):
        if _index_exists(idx):
            op.drop_index(idx, table_name="facturas_recibidas")
    if _table_exists("facturas_recibidas"):
        op.drop_table("facturas_recibidas")
