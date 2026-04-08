"""empresa_eva_account_link

Adds two columns to the ``empresas`` table to support the
silent-channel-health plan:

- ``eva_account_id`` (UUID, nullable) — cross-DB pointer to an Eva
  customer account. No FK constraint because Eva ERP and Eva live in
  different databases.
- ``auto_match_attempted`` (bool, default false) — flag set after the
  auto-match-by-name routine has run for an empresa, regardless of
  result. Prevents the routine from re-running on every page load
  AND prevents it from clobbering manual links the user cleared on
  purpose.

Plan: docs/domains/integrations/instagram/plan-silent-channel-health.md

NOTE: this migration is intentionally minimal. The ``--autogenerate``
output detected unrelated pre-existing drift between Eva ERP's
models and the local DB schema (consumed_sso_tokens, alter_column
non-null defaults, index drops on facturas/tasks/empresa_*). That
drift is NOT caused by this plan and is left out of this revision so
this migration only does what its name says.

Revision ID: 47945ef287dd
Revises: p5q6r7s8t9u0
Create Date: 2026-04-08 09:05:13.704347
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "47945ef287dd"
down_revision: Union[str, None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column("eva_account_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "empresas",
        sa.Column(
            "auto_match_attempted",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("empresas", "auto_match_attempted")
    op.drop_column("empresas", "eva_account_id")
