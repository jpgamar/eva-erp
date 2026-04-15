"""empresa stripe billing fields

Revision ID: q6r7s8t9u0v1
Revises: 47945ef287dd
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, None] = "47945ef287dd"
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
    if not _column_exists("empresas", "stripe_customer_id"):
        op.add_column("empresas", sa.Column("stripe_customer_id", sa.String(255), nullable=True, unique=True))
    if not _column_exists("empresas", "stripe_subscription_id"):
        op.add_column("empresas", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    if not _column_exists("empresas", "subscription_status"):
        op.add_column("empresas", sa.Column("subscription_status", sa.String(30), nullable=True))
    if not _column_exists("empresas", "current_period_end"):
        op.add_column("empresas", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists("empresas", "billing_recipient_emails"):
        # server_default wrapped via sa.text so asyncpg doesn't try to JSON-parse
        # the literal (Phase 2 drive-by; prod worked because it never boots from scratch).
        op.add_column(
            "empresas",
            sa.Column("billing_recipient_emails", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        )


def downgrade() -> None:
    op.drop_column("empresas", "billing_recipient_emails")
    op.drop_column("empresas", "current_period_end")
    op.drop_column("empresas", "subscription_status")
    op.drop_column("empresas", "stripe_subscription_id")
    op.drop_column("empresas", "stripe_customer_id")
