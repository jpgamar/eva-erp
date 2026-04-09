"""empresa fiscal fields for CFDI

Revision ID: r7s8t9u0v1w2
Revises: q6r7s8t9u0v1
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r7s8t9u0v1w2"
down_revision: Union[str, None] = "q6r7s8t9u0v1"
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


def upgrade() -> None:
    if not _column_exists("empresas", "fiscal_postal_code"):
        op.add_column("empresas", sa.Column("fiscal_postal_code", sa.String(5), nullable=True))
    if not _column_exists("empresas", "cfdi_use"):
        op.add_column("empresas", sa.Column("cfdi_use", sa.String(10), nullable=True, server_default="G03"))
    if not _column_exists("empresas", "person_type"):
        op.add_column("empresas", sa.Column("person_type", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "person_type")
    op.drop_column("empresas", "cfdi_use")
    op.drop_column("empresas", "fiscal_postal_code")
