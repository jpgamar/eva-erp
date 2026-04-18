"""add outbox pattern columns to facturas for atomic CFDI stamping

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-04-18

Context: On 2026-04-18 we discovered a data-loss bug where factura F-4
(SERVIACERO COMERCIAL, 2026-03-23) was stamped successfully by FacturAPI
but the INSERT into `facturas` was rolled back. Root cause: the auto-commit
in get_db() can fail AFTER FacturAPI responds, leaving a valid CFDI in SAT
with no trace in the ERP database.

This migration adds the columns needed for the outbox pattern:
  1. Write row with status='pending_stamp' + idempotency_key BEFORE calling FacturAPI.
  2. Commit immediately (the row is now durable).
  3. A worker picks up pending rows, calls FacturAPI with the idempotency_key,
     and updates the row to status='valid' (or retries on failure).

The `facturapi_idempotency_key` is the bridge: even if FacturAPI stamps and
our DB update fails, the next retry sends the same key and (per FacturAPI
docs) receives the same CFDI back — no duplicate.

The `(status, next_retry_at)` index supports the worker's poll query:
    SELECT * FROM facturas
    WHERE status = 'pending_stamp'
      AND (next_retry_at IS NULL OR next_retry_at <= now())
    ORDER BY next_retry_at NULLS FIRST
    LIMIT 10
    FOR UPDATE SKIP LOCKED
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w2x3y4z5a6b7"
down_revision: Union[str, None] = "v1w2x3y4z5a6"
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


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.first() is not None


def upgrade() -> None:
    if not _column_exists("facturas", "facturapi_idempotency_key"):
        op.add_column(
            "facturas",
            sa.Column("facturapi_idempotency_key", sa.String(64), nullable=True),
        )
        op.create_index(
            "uq_facturas_facturapi_idempotency_key",
            "facturas",
            ["facturapi_idempotency_key"],
            unique=True,
        )

    if not _column_exists("facturas", "stamp_retry_count"):
        op.add_column(
            "facturas",
            sa.Column(
                "stamp_retry_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    if not _column_exists("facturas", "last_stamp_error"):
        op.add_column(
            "facturas",
            sa.Column("last_stamp_error", sa.Text(), nullable=True),
        )

    if not _column_exists("facturas", "next_retry_at"):
        op.add_column(
            "facturas",
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists("facturas", "stamp_attempted_at"):
        op.add_column(
            "facturas",
            sa.Column("stamp_attempted_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Worker pickup index: finds pending_stamp rows whose next_retry_at has arrived
    # (or is NULL, meaning never attempted). ORDER BY next_retry_at NULLS FIRST means
    # new pending rows process before retried ones.
    if not _index_exists("ix_facturas_outbox_pickup"):
        op.create_index(
            "ix_facturas_outbox_pickup",
            "facturas",
            ["status", "next_retry_at"],
            postgresql_where=sa.text("status IN ('pending_stamp', 'stamp_failed')"),
        )


def downgrade() -> None:
    if _index_exists("ix_facturas_outbox_pickup"):
        op.drop_index("ix_facturas_outbox_pickup", table_name="facturas")
    if _column_exists("facturas", "stamp_attempted_at"):
        op.drop_column("facturas", "stamp_attempted_at")
    if _column_exists("facturas", "next_retry_at"):
        op.drop_column("facturas", "next_retry_at")
    if _column_exists("facturas", "last_stamp_error"):
        op.drop_column("facturas", "last_stamp_error")
    if _column_exists("facturas", "stamp_retry_count"):
        op.drop_column("facturas", "stamp_retry_count")
    if _index_exists("uq_facturas_facturapi_idempotency_key"):
        op.drop_index(
            "uq_facturas_facturapi_idempotency_key",
            table_name="facturas",
        )
    if _column_exists("facturas", "facturapi_idempotency_key"):
        op.drop_column("facturas", "facturapi_idempotency_key")
