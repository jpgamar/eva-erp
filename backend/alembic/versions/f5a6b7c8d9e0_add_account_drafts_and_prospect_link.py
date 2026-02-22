"""add_account_drafts_and_prospect_link

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-02-22 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False, server_default="COMMERCE"),
        sa.Column("owner_email", sa.String(255), nullable=False),
        sa.Column("owner_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("partner_id", UUID(as_uuid=True), nullable=True),
        sa.Column("plan_tier", sa.String(50), nullable=False, server_default="STANDARD"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="MONTHLY"),
        sa.Column("facturapi_org_api_key", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("prospect_id", UUID(as_uuid=True), sa.ForeignKey("prospects.id"), nullable=True),
        sa.Column("provisioned_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add converted_to_draft_id to prospects
    op.add_column(
        "prospects",
        sa.Column("converted_to_draft_id", UUID(as_uuid=True), sa.ForeignKey("account_drafts.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prospects", "converted_to_draft_id")
    op.drop_table("account_drafts")
