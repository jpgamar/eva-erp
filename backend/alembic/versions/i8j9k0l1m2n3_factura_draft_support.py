"""factura draft support

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # facturapi_id becomes nullable (drafts have no Facturapi record yet)
    op.alter_column("facturas", "facturapi_id", existing_type=sa.String(255), nullable=True)

    # Default status changes from 'valid' to 'draft'
    op.alter_column(
        "facturas", "status",
        existing_type=sa.String(20),
        server_default="draft",
    )

    # New columns needed to rebuild Facturapi payload at stamp time
    op.add_column("facturas", sa.Column("customer_tax_system", sa.String(5), nullable=True))
    op.add_column("facturas", sa.Column("customer_zip", sa.String(5), nullable=True))
    op.add_column("facturas", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("facturas", "notes")
    op.drop_column("facturas", "customer_zip")
    op.drop_column("facturas", "customer_tax_system")

    op.alter_column(
        "facturas", "status",
        existing_type=sa.String(20),
        server_default="valid",
    )

    op.alter_column("facturas", "facturapi_id", existing_type=sa.String(255), nullable=False)
