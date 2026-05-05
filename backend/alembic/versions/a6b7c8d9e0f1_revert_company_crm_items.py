"""revert empresa_items CRM todo and calendar fields

Revision ID: a6b7c8d9e0f1
Revises: z5a6b7c8d9e0
Create Date: 2026-05-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "z5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).first()
        is not None
    )


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"), {"name": name}).first() is not None


def _constraint_exists(name: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name"), {"name": name}).first()
        is not None
    )


def upgrade() -> None:
    for index_name in (
        "ix_empresa_items_empresa_done",
        "ix_empresa_items_assigned_to",
        "ix_empresa_items_start_at",
        "ix_empresa_items_due_at",
    ):
        if _index_exists(index_name):
            op.drop_index(index_name, table_name="empresa_items")

    with op.batch_alter_table("empresa_items") as batch:
        if _constraint_exists("fk_empresa_items_assigned_to_users"):
            batch.drop_constraint("fk_empresa_items_assigned_to_users", type_="foreignkey")
        for column in (
            "completed_at",
            "assigned_to",
            "reminder_at",
            "end_at",
            "start_at",
            "due_at",
            "contact_method",
            "description",
            "kind",
        ):
            if _column_exists("empresa_items", column):
                batch.drop_column(column)


def downgrade() -> None:
    with op.batch_alter_table("empresa_items") as batch:
        if not _column_exists("empresa_items", "kind"):
            batch.add_column(sa.Column("kind", sa.String(length=20), nullable=False, server_default="todo"))
        if not _column_exists("empresa_items", "description"):
            batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        if not _column_exists("empresa_items", "contact_method"):
            batch.add_column(sa.Column("contact_method", sa.String(length=30), nullable=True))
        if not _column_exists("empresa_items", "due_at"):
            batch.add_column(sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("empresa_items", "start_at"):
            batch.add_column(sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("empresa_items", "end_at"):
            batch.add_column(sa.Column("end_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("empresa_items", "reminder_at"):
            batch.add_column(sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("empresa_items", "assigned_to"):
            batch.add_column(sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True))
        if not _column_exists("empresa_items", "completed_at"):
            batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE empresa_items SET completed_at = updated_at WHERE done IS TRUE AND completed_at IS NULL")

    if not _constraint_exists("fk_empresa_items_assigned_to_users"):
        with op.batch_alter_table("empresa_items") as batch:
            batch.create_foreign_key(
                "fk_empresa_items_assigned_to_users",
                "users",
                ["assigned_to"],
                ["id"],
            )

    if not _index_exists("ix_empresa_items_due_at"):
        op.create_index("ix_empresa_items_due_at", "empresa_items", ["due_at"])
    if not _index_exists("ix_empresa_items_start_at"):
        op.create_index("ix_empresa_items_start_at", "empresa_items", ["start_at"])
    if not _index_exists("ix_empresa_items_assigned_to"):
        op.create_index("ix_empresa_items_assigned_to", "empresa_items", ["assigned_to"])
    if not _index_exists("ix_empresa_items_empresa_done"):
        op.create_index("ix_empresa_items_empresa_done", "empresa_items", ["empresa_id", "done"])
