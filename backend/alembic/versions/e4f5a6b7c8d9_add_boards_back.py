"""add_boards_back

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5g6h7i8
Create Date: 2026-02-21 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5g6h7i8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Simplified boards — just a name/slug for grouping tasks
    op.create_table(
        "boards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # Optional board_id on tasks
    op.add_column(
        "tasks",
        sa.Column("board_id", sa.UUID(), sa.ForeignKey("boards.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_tasks_board_id", "tasks", ["board_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_board_id", table_name="tasks")
    op.drop_column("tasks", "board_id")
    op.drop_table("boards")
