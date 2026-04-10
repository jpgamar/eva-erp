"""widen payment_link token column to 30 chars

Revision ID: t9u0v1w2x3y4
Revises: s8t9u0v1w2x3
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t9u0v1w2x3y4"
down_revision: Union[str, None] = "s8t9u0v1w2x3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("payment_links", "token", type_=sa.String(30), existing_type=sa.String(20))


def downgrade() -> None:
    op.alter_column("payment_links", "token", type_=sa.String(20), existing_type=sa.String(30))
