"""add cedular retention fields to facturas + eva_billing_records

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, None] = "u0v1w2x3y4z5"
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
    # facturas: track the state-level cedular retention separately from
    # the two federal retentions already stored on the row.
    if not _column_exists("facturas", "local_retention"):
        op.add_column(
            "facturas",
            sa.Column(
                "local_retention",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="0",
            ),
        )
    if not _column_exists("facturas", "local_retention_state"):
        op.add_column(
            "facturas",
            sa.Column("local_retention_state", sa.String(3), nullable=True),
        )
    if not _column_exists("facturas", "local_retention_rate"):
        op.add_column(
            "facturas",
            sa.Column("local_retention_rate", sa.Numeric(5, 4), nullable=True),
        )

    # eva_billing_records: mirror the cedular amount for reconciliation.
    # We also expose state + rate in metadata_json, but a dedicated column
    # makes ad-hoc SQL queries (monthly totals, etc.) trivial.
    if not _column_exists("eva_billing_records", "cedular_retention"):
        op.add_column(
            "eva_billing_records",
            sa.Column("cedular_retention", sa.Numeric(12, 2), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("eva_billing_records", "cedular_retention"):
        op.drop_column("eva_billing_records", "cedular_retention")
    if _column_exists("facturas", "local_retention_rate"):
        op.drop_column("facturas", "local_retention_rate")
    if _column_exists("facturas", "local_retention_state"):
        op.drop_column("facturas", "local_retention_state")
    if _column_exists("facturas", "local_retention"):
        op.drop_column("facturas", "local_retention")
