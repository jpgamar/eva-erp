"""rename_mxn_columns_to_usd

Revision ID: a1b2c3d4e5f6
Revises: ff7e26d724ef
Create Date: 2026-02-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ff7e26d724ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("income_entries", "amount_mxn", new_column_name="amount_usd")
    op.alter_column("expenses", "amount_mxn", new_column_name="amount_usd")
    op.alter_column("invoices", "total_mxn", new_column_name="total_usd")
    op.alter_column("cash_balances", "amount_mxn", new_column_name="amount_usd")
    op.alter_column("customers", "mrr_mxn", new_column_name="mrr_usd")
    op.alter_column("customers", "lifetime_value_mxn", new_column_name="lifetime_value_usd")
    op.alter_column("prospects", "estimated_mrr_mxn", new_column_name="estimated_mrr_usd")
    op.alter_column("credentials", "monthly_cost_mxn", new_column_name="monthly_cost_usd")
    op.alter_column("kpi_snapshots", "total_expenses_mxn", new_column_name="total_expenses_usd")


def downgrade() -> None:
    op.alter_column("income_entries", "amount_usd", new_column_name="amount_mxn")
    op.alter_column("expenses", "amount_usd", new_column_name="amount_mxn")
    op.alter_column("invoices", "total_usd", new_column_name="total_mxn")
    op.alter_column("cash_balances", "amount_usd", new_column_name="amount_mxn")
    op.alter_column("customers", "mrr_usd", new_column_name="mrr_mxn")
    op.alter_column("customers", "lifetime_value_usd", new_column_name="lifetime_value_mxn")
    op.alter_column("prospects", "estimated_mrr_usd", new_column_name="estimated_mrr_mxn")
    op.alter_column("credentials", "monthly_cost_usd", new_column_name="monthly_cost_mxn")
    op.alter_column("kpi_snapshots", "total_expenses_usd", new_column_name="total_expenses_mxn")
