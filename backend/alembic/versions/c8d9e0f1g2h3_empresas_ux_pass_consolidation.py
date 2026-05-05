"""empresas UX pass: nullable empresa_id, reminder columns, tasks consolidation

Plan: docs/domains/crm/plan-empresas-ux-pass.md

This migration:
1. Adds reminder_24h_sent_at, reminder_1h_sent_at columns to empresa_items.
2. Drops NOT NULL on empresa_items.empresa_id (internal/non-empresa tasks
   live in the same table now).
3. Backfills `tasks` rows into `empresa_items` with empresa_id=NULL,
   kind='todo'. Preserves: id, title, description, due_date→due_at,
   status='done'→done+completed_at, created_by, assignee_id→assigned_to,
   timestamps.
4. **Lossy:** priority, labels, source_meeting_id, board_id are NOT
   migrated (no destination columns). Documented in run-book.
5. Folds the latest task_comments row into description (only the
   most recent comment is preserved; older comments are deleted with
   `task_comments`).
6. Stamps `reminder_24h_sent_at` + `reminder_1h_sent_at` to NOW for
   any item whose start_at OR backfilled due_at is already in the past
   (reminder dispatcher must never email a past event).
7. Drops `task_comments`, `tasks`, and `boards` tables.

Revision ID: c8d9e0f1g2h3
Revises: b8c9d0e1f2g3
Create Date: 2026-05-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8d9e0f1g2h3"
down_revision: Union[str, None] = "b8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).first()
        is not None
    )


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :table"),
            {"table": table},
        ).first()
        is not None
    )


def upgrade() -> None:
    # 1. Add reminder columns + drop NOT NULL on empresa_id (idempotent)
    if not _column_exists("empresa_items", "reminder_24h_sent_at"):
        op.add_column(
            "empresa_items",
            sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("empresa_items", "reminder_1h_sent_at"):
        op.add_column(
            "empresa_items",
            sa.Column("reminder_1h_sent_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.alter_column(
        "empresa_items",
        "empresa_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 2. Backfill tasks → empresa_items (only if tasks exists)
    if _table_exists("tasks"):
        # 2a. Fold latest comment into description (lossy: older comments lost)
        if _table_exists("task_comments"):
            op.execute(
                """
                UPDATE tasks t
                   SET description = COALESCE(t.description, '')
                       || CASE
                            WHEN t.description IS NOT NULL AND t.description <> ''
                            THEN E'\n\n---\n'
                            ELSE ''
                          END
                       || 'Last comment: ' || c.content
                  FROM (
                    SELECT DISTINCT ON (task_id) task_id, content
                      FROM task_comments
                     ORDER BY task_id, created_at DESC
                  ) c
                 WHERE c.task_id = t.id
                   AND COALESCE(t.description, '') NOT LIKE '%Last comment:%';
                """
            )
            op.execute("DROP TABLE task_comments CASCADE;")

        # 2b. Backfill into empresa_items. ON CONFLICT keeps the migration
        # idempotent under partial-state retries.
        op.execute(
            """
            INSERT INTO empresa_items (
                id, empresa_id, title, description, kind, due_at,
                done, completed_at,
                created_by, created_at, updated_at, assigned_to,
                reminder_24h_sent_at, reminder_1h_sent_at
            )
            SELECT
                id,
                NULL AS empresa_id,
                title,
                description,
                'todo' AS kind,
                CASE
                    WHEN due_date IS NULL THEN NULL
                    ELSE (due_date::timestamp + interval '23 hours 59 minutes')
                         AT TIME ZONE 'America/Mexico_City'
                END AS due_at,
                (status = 'done') AS done,
                CASE WHEN status = 'done' THEN updated_at END AS completed_at,
                created_by,
                created_at,
                updated_at,
                assignee_id,
                CASE
                    WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN NOW()
                END AS reminder_24h_sent_at,
                CASE
                    WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN NOW()
                END AS reminder_1h_sent_at
            FROM tasks
            ON CONFLICT (id) DO NOTHING;
            """
        )
        op.execute("DROP TABLE tasks CASCADE;")

    if _table_exists("boards"):
        op.execute("DROP TABLE boards CASCADE;")

    # 3. Sentinel pass for any pre-existing empresa_items rows whose
    # start_at is already in the past — never email reminders for them.
    op.execute(
        """
        UPDATE empresa_items
           SET reminder_24h_sent_at = COALESCE(reminder_24h_sent_at, NOW()),
               reminder_1h_sent_at  = COALESCE(reminder_1h_sent_at,  NOW())
         WHERE start_at IS NOT NULL
           AND start_at < NOW();
        """
    )


def downgrade() -> None:
    """Restore the schema only — task data backfilled into empresa_items
    is NOT extracted back. Documented data loss; the up-migration's run-book
    requires a manual export of `tasks` BEFORE applying if rollback is a
    real concern.
    """
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS boards (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            board_id UUID REFERENCES boards(id) ON DELETE SET NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'todo',
            assignee_id UUID REFERENCES users(id),
            priority VARCHAR(20) DEFAULT 'medium',
            due_date DATE,
            labels TEXT[],
            source_meeting_id UUID,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS task_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.alter_column(
        "empresa_items",
        "empresa_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    if _column_exists("empresa_items", "reminder_1h_sent_at"):
        op.drop_column("empresa_items", "reminder_1h_sent_at")
    if _column_exists("empresa_items", "reminder_24h_sent_at"):
        op.drop_column("empresa_items", "reminder_24h_sent_at")
