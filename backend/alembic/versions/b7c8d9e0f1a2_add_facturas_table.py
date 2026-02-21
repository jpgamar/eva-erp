"""add_facturas_table

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-20 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "facturas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facturapi_id", sa.String(255), unique=True, nullable=False),
        sa.Column("cfdi_uuid", sa.String(255), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_rfc", sa.String(13), nullable=False),
        sa.Column("use", sa.String(10), nullable=False),
        sa.Column("payment_form", sa.String(5), nullable=False),
        sa.Column("payment_method", sa.String(5), server_default="PUE"),
        sa.Column("line_items_json", postgresql.JSONB(), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="MXN"),
        sa.Column("status", sa.String(20), server_default="valid"),
        sa.Column("cancellation_status", sa.String(50), nullable=True),
        sa.Column("pdf_url", sa.String(512), nullable=True),
        sa.Column("xml_url", sa.String(512), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("series", sa.String(25), nullable=True),
        sa.Column("folio_number", sa.Integer(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("facturas")
