"""empresa stripe billing fields

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("stripe_customer_id", sa.String(255), nullable=True, unique=True))
    op.add_column("empresas", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.add_column("empresas", sa.Column("subscription_status", sa.String(30), nullable=True))
    op.add_column("empresas", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("empresas", sa.Column("billing_recipient_emails", JSONB, nullable=False, server_default="'[]'::jsonb"))


def downgrade() -> None:
    op.drop_column("empresas", "billing_recipient_emails")
    op.drop_column("empresas", "current_period_end")
    op.drop_column("empresas", "subscription_status")
    op.drop_column("empresas", "stripe_subscription_id")
    op.drop_column("empresas", "stripe_customer_id")
