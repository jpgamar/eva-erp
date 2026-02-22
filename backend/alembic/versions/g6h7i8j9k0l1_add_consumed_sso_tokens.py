"""add consumed_sso_tokens

Revision ID: g6h7i8j9k0l1
Revises: f5a6b7c8d9e0
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g6h7i8j9k0l1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE consumed_sso_tokens (
            jti VARCHAR(36) PRIMARY KEY,
            consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_consumed_sso_tokens_consumed_at ON consumed_sso_tokens (consumed_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_consumed_sso_tokens_consumed_at")
    op.execute("DROP TABLE IF EXISTS consumed_sso_tokens")
