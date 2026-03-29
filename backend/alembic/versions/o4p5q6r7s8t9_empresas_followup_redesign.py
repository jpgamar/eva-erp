"""empresas followup redesign

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to empresas
    op.add_column("empresas", sa.Column("status", sa.String(30), nullable=False, server_default="operativo"))
    op.add_column("empresas", sa.Column("ball_on", sa.String(10), nullable=True))
    op.add_column("empresas", sa.Column("summary_note", sa.Text(), nullable=True))

    # Simplify empresa_items: drop old columns, add done
    op.drop_column("empresa_items", "type")
    op.drop_column("empresa_items", "description")
    op.drop_column("empresa_items", "status")
    op.drop_column("empresa_items", "priority")
    op.drop_column("empresa_items", "due_date")
    op.add_column("empresa_items", sa.Column("done", sa.Boolean(), nullable=False, server_default="false"))

    # Create empresa_history table
    op.create_table(
        "empresa_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("empresa_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_changed", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_empresa_history_empresa_id", "empresa_history", ["empresa_id"])


def downgrade() -> None:
    op.drop_index("ix_empresa_history_empresa_id", table_name="empresa_history")
    op.drop_table("empresa_history")

    op.drop_column("empresa_items", "done")
    op.add_column("empresa_items", sa.Column("type", sa.String(10), nullable=False, server_default="need"))
    op.add_column("empresa_items", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("empresa_items", sa.Column("status", sa.String(20), server_default="open"))
    op.add_column("empresa_items", sa.Column("priority", sa.String(10), nullable=True))
    op.add_column("empresa_items", sa.Column("due_date", sa.Date(), nullable=True))

    op.drop_column("empresas", "summary_note")
    op.drop_column("empresas", "ball_on")
    op.drop_column("empresas", "status")
