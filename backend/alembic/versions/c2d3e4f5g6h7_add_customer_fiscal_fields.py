"""add_customer_fiscal_fields

Revision ID: c2d3e4f5g6h7
Revises: b7c8d9e0f1a2
Create Date: 2026-02-20 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5g6h7"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Fiscal columns on customers --
    op.add_column("customers", sa.Column("legal_name", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("rfc", sa.String(13), nullable=True))
    op.add_column("customers", sa.Column("tax_regime", sa.String(5), nullable=True))
    op.add_column("customers", sa.Column("fiscal_zip", sa.String(5), nullable=True))
    op.add_column("customers", sa.Column("default_cfdi_use", sa.String(5), nullable=True))
    op.add_column("customers", sa.Column("fiscal_email", sa.String(255), nullable=True))

    # -- Link facturas → customers --
    op.add_column(
        "facturas",
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_facturas_customer_id", "facturas", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_facturas_customer_id", table_name="facturas")
    op.drop_column("facturas", "customer_id")
    op.drop_column("customers", "fiscal_email")
    op.drop_column("customers", "default_cfdi_use")
    op.drop_column("customers", "fiscal_zip")
    op.drop_column("customers", "tax_regime")
    op.drop_column("customers", "rfc")
    op.drop_column("customers", "legal_name")
