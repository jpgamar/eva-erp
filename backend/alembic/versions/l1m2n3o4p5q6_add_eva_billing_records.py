"""add eva billing bridge records

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eva_billing_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_charge_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("factura_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_stamp"),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("email_status", sa.String(length=30), nullable=True),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("isr_retention", sa.Numeric(12, 2), nullable=True),
        sa.Column("iva_retention", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["factura_id"], ["facturas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_eva_billing_records_idempotency_key"),
    )
    op.create_index("ix_eva_billing_records_account_id", "eva_billing_records", ["account_id"])
    op.create_index("ix_eva_billing_records_stripe_invoice_id", "eva_billing_records", ["stripe_invoice_id"])
    op.create_index(
        "ix_eva_billing_records_stripe_payment_intent_id",
        "eva_billing_records",
        ["stripe_payment_intent_id"],
    )
    op.create_index("ix_eva_billing_records_stripe_charge_id", "eva_billing_records", ["stripe_charge_id"])


def downgrade() -> None:
    op.drop_index("ix_eva_billing_records_stripe_charge_id", table_name="eva_billing_records")
    op.drop_index("ix_eva_billing_records_stripe_payment_intent_id", table_name="eva_billing_records")
    op.drop_index("ix_eva_billing_records_stripe_invoice_id", table_name="eva_billing_records")
    op.drop_index("ix_eva_billing_records_account_id", table_name="eva_billing_records")
    op.drop_table("eva_billing_records")
