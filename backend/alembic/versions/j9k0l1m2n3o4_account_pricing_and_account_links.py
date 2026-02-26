"""add account pricing profiles and account links

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("income_entries", sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("facturas", sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.add_column("account_drafts", sa.Column("billing_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "account_drafts",
        sa.Column("billing_currency", sa.String(length=3), nullable=False, server_default="MXN"),
    )
    op.add_column(
        "account_drafts",
        sa.Column("is_billable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "account_pricing_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("billing_currency", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("billing_interval", sa.String(length=20), nullable=False, server_default="MONTHLY"),
        sa.Column("is_billable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_account_pricing_profiles_account_id"),
    )


def downgrade() -> None:
    op.drop_table("account_pricing_profiles")

    op.drop_column("account_drafts", "is_billable")
    op.drop_column("account_drafts", "billing_currency")
    op.drop_column("account_drafts", "billing_amount")

    op.drop_column("facturas", "account_id")
    op.drop_column("income_entries", "account_id")
