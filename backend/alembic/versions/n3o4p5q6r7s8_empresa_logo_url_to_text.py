"""empresa logo_url to text

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("empresas", "logo_url", type_=sa.Text(), existing_type=sa.String(512))


def downgrade() -> None:
    op.alter_column("empresas", "logo_url", type_=sa.String(512), existing_type=sa.Text())
