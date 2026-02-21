"""simplify_tasks

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-02-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d3e4f5g6h7i8"
down_revision: Union[str, None] = "c2d3e4f5g6h7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add status column with server default
    op.add_column(
        "tasks",
        sa.Column("status", sa.String(20), server_default="todo", nullable=False),
    )

    # 2. Data-migrate: map column names to status values
    op.execute(
        """
        UPDATE tasks SET status = 'done'
        WHERE column_id IN (SELECT id FROM columns WHERE name = 'Done')
        """
    )
    op.execute(
        """
        UPDATE tasks SET status = 'in_progress'
        WHERE column_id IN (SELECT id FROM columns WHERE name = 'In Progress')
        """
    )
    # Everything else stays as 'todo' (the server_default)

    # 3. Drop FK constraints from tasks
    op.drop_constraint("tasks_column_id_fkey", "tasks", type_="foreignkey")
    op.drop_constraint("tasks_board_id_fkey", "tasks", type_="foreignkey")

    # 4. Drop columns from tasks
    op.drop_column("tasks", "column_id")
    op.drop_column("tasks", "board_id")
    op.drop_column("tasks", "position")

    # 5. Drop dependent tables (order matters)
    op.drop_table("task_activities")
    op.drop_table("columns")
    op.drop_table("boards")

    # 6. Add index on status
    op.create_index("ix_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tasks_status", table_name="tasks")

    # Recreate boards
    op.create_table(
        "boards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # Recreate columns
    op.create_table(
        "columns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("board_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate task_activities
    op.create_table(
        "task_activities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add back columns to tasks
    op.add_column("tasks", sa.Column("position", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("board_id", sa.UUID(), nullable=True))
    op.add_column("tasks", sa.Column("column_id", sa.UUID(), nullable=True))
    op.create_foreign_key("tasks_board_id_fkey", "tasks", "boards", ["board_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("tasks_column_id_fkey", "tasks", "columns", ["column_id"], ["id"], ondelete="CASCADE")

    # Drop status column
    op.drop_column("tasks", "status")
