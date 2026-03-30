"""empresa payment fields

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-03-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("empresas", sa.Column("payment_day", sa.Integer(), nullable=True))
    op.add_column("empresas", sa.Column("last_paid_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "last_paid_date")
    op.drop_column("empresas", "payment_day")
    op.drop_column("empresas", "monthly_amount")
