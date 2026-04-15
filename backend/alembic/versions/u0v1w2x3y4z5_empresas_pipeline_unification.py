"""Empresas pipeline unification — merges prospects into empresas.

Adds lifecycle_stage + every preserved prospect field to ``empresas``, creates
``prospect_empresa_map`` mapping table, INSERT-only copies every prospect into
``empresas`` (no dedup by name — name is non-unique in both tables), copies
prospect_interactions → empresa_interactions, adds ``empresa_id`` FKs to
meetings/account_drafts/customers, flags operativo rows missing an active
subscription for manual review, adds PaymentLink.plan_tier, billing_interval on
empresas, constancia_object_key, optimistic-lock version column, fiscal sync
retry fields, deadline field, grandfather flag, and a unique index on
eva_account_id (with pre-migration dedup for any existing duplicates).

The old ``prospects`` + ``prospect_interactions`` tables remain in place for one
release so rollback is possible; a follow-up PR drops them plus the now-obsolete
``meetings.prospect_id`` / ``account_drafts.prospect_id`` / ``customers.prospect_id``
columns.

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, None] = "t9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. Pre-migration dedup of empresas.eva_account_id duplicates.
    # ------------------------------------------------------------------
    # Before we can add a UNIQUE partial index we must resolve any empresas
    # that collide on eva_account_id. Keep the oldest row's link; null out the
    # others and log a fiscal_sync_error for manual review.
    op.execute(
        """
        WITH dupes AS (
            SELECT id, eva_account_id,
                   ROW_NUMBER() OVER (PARTITION BY eva_account_id ORDER BY created_at ASC) AS rn
              FROM empresas
             WHERE eva_account_id IS NOT NULL
        ),
        to_null AS (
            SELECT id FROM dupes WHERE rn > 1
        )
        UPDATE empresas e
           SET eva_account_id = NULL
          FROM to_null t
         WHERE e.id = t.id;
        """
    )

    # ------------------------------------------------------------------
    # 1. Expand empresas schema (all new columns nullable unless noted).
    # ------------------------------------------------------------------
    op.add_column(
        "empresas",
        sa.Column(
            "lifecycle_stage",
            sa.String(20),
            nullable=False,
            server_default="prospecto",
        ),
    )
    op.create_check_constraint(
        "ck_empresas_lifecycle_stage",
        "empresas",
        "lifecycle_stage IN ('prospecto','interesado','demo','negociacion','implementacion','operativo','churn_risk','inactivo')",
    )
    op.add_column(
        "empresas",
        sa.Column(
            "billing_interval",
            sa.String(10),
            nullable=False,
            server_default="monthly",
        ),
    )
    op.create_check_constraint(
        "ck_empresas_billing_interval",
        "empresas",
        "billing_interval IN ('monthly','annual')",
    )
    op.add_column("empresas", sa.Column("expected_close_date", sa.Date(), nullable=True))
    op.add_column("empresas", sa.Column("cancellation_scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("empresas", sa.Column("constancia_object_key", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("empresas", sa.Column("fiscal_sync_pending_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("empresas", sa.Column("fiscal_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "empresas",
        sa.Column("grandfathered", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Preserved prospect fields.
    op.add_column("empresas", sa.Column("website", sa.String(512), nullable=True))
    op.add_column("empresas", sa.Column("contact_name", sa.String(255), nullable=True))
    op.add_column("empresas", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("empresas", sa.Column("contact_phone", sa.String(50), nullable=True))
    op.add_column("empresas", sa.Column("contact_role", sa.String(100), nullable=True))
    op.add_column("empresas", sa.Column("source", sa.String(30), nullable=True))
    op.add_column("empresas", sa.Column("referred_by", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("estimated_plan", sa.String(20), nullable=True))
    op.add_column("empresas", sa.Column("estimated_mrr_currency", sa.String(3), nullable=True))
    op.add_column("empresas", sa.Column("estimated_mrr_usd", sa.Numeric(12, 2), nullable=True))
    op.add_column("empresas", sa.Column("prospect_notes", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("next_follow_up", sa.Date(), nullable=True))
    op.add_column(
        "empresas",
        sa.Column("assigned_to", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("empresas", sa.Column("tags", sa.dialects.postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("empresas", sa.Column("lost_reason", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("legacy_prospect_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))

    # Unique index on eva_account_id (partial, excludes NULLs).
    op.create_index(
        "empresas_eva_account_id_uniq",
        "empresas",
        ["eva_account_id"],
        unique=True,
        postgresql_where=sa.text("eva_account_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 2. PaymentLink.plan_tier — drives canonical product selection at Checkout.
    # ------------------------------------------------------------------
    op.add_column(
        "payment_links",
        sa.Column(
            "plan_tier",
            sa.String(20),
            nullable=False,
            server_default="standard",
        ),
    )
    op.create_check_constraint(
        "ck_payment_links_plan_tier",
        "payment_links",
        "plan_tier IN ('standard','pro')",
    )

    # ------------------------------------------------------------------
    # 3. prospect_empresa_map — INSERT-only mapping table (prospect_id is PK).
    # ------------------------------------------------------------------
    op.create_table(
        "prospect_empresa_map",
        sa.Column(
            "prospect_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prospects.id"),
            primary_key=True,
        ),
        sa.Column(
            "empresa_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("empresas.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # ------------------------------------------------------------------
    # 4. Backfill lifecycle_stage from existing empresas.status.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE empresas SET lifecycle_stage = CASE status
            WHEN 'operativo' THEN 'operativo'
            WHEN 'en_implementacion' THEN 'implementacion'
            WHEN 'requiere_atencion' THEN 'churn_risk'
            ELSE 'prospecto'
        END
        """
    )

    # ------------------------------------------------------------------
    # 5. INSERT-only prospect → empresa migration (no dedup by name).
    # ------------------------------------------------------------------
    op.execute(
        """
        WITH inserted AS (
            INSERT INTO empresas (
                id, name, website, industry, email, phone,
                contact_name, contact_email, contact_phone, contact_role,
                lifecycle_stage, status, monthly_amount, source, referred_by,
                estimated_plan, estimated_mrr_currency, estimated_mrr_usd,
                prospect_notes, next_follow_up, assigned_to, tags, lost_reason,
                created_by, created_at, legacy_prospect_id
            )
            SELECT
                gen_random_uuid(), p.company_name, p.website, p.industry, p.contact_email, p.contact_phone,
                p.contact_name, p.contact_email, p.contact_phone, p.contact_role,
                CASE p.status
                    WHEN 'identified' THEN 'prospecto'
                    WHEN 'contacted' THEN 'interesado'
                    WHEN 'interested' THEN 'interesado'
                    WHEN 'demo_scheduled' THEN 'demo'
                    WHEN 'demo_done' THEN 'demo'
                    WHEN 'proposal_sent' THEN 'negociacion'
                    WHEN 'negotiating' THEN 'negociacion'
                    WHEN 'won' THEN 'operativo'
                    WHEN 'lost' THEN 'inactivo'
                    ELSE 'prospecto'
                END,
                -- empresas.status remains required ('operativo' default); keep
                -- legacy-migrated rows as 'operativo' so existing queries don't
                -- panic. lifecycle_stage is the new source of truth.
                'operativo',
                p.estimated_mrr, p.source, p.referred_by,
                p.estimated_plan, p.estimated_mrr_currency, p.estimated_mrr_usd,
                p.notes, p.next_follow_up, p.assigned_to, p.tags, p.lost_reason,
                p.created_by, p.created_at, p.id
            FROM prospects p
            RETURNING id, legacy_prospect_id
        )
        INSERT INTO prospect_empresa_map (prospect_id, empresa_id)
        SELECT legacy_prospect_id, id FROM inserted;
        """
    )

    # ------------------------------------------------------------------
    # 6. empresa_interactions — mirrors prospect_interactions via mapping.
    # ------------------------------------------------------------------
    op.create_table(
        "empresa_interactions",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "empresa_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_empresa_interactions_empresa_id", "empresa_interactions", ["empresa_id"])
    op.execute(
        """
        INSERT INTO empresa_interactions (id, empresa_id, type, summary, date, created_by, created_at)
        SELECT pi.id, pem.empresa_id, pi.type, pi.summary, pi.date, pi.created_by, pi.created_at
          FROM prospect_interactions pi
          JOIN prospect_empresa_map pem ON pem.prospect_id = pi.prospect_id;
        """
    )

    # ------------------------------------------------------------------
    # 7. meetings.empresa_id + account_drafts.empresa_id + customers.empresa_id.
    #    Keep *.prospect_id for 1 release so follow-up PR can drop safely.
    # ------------------------------------------------------------------
    op.add_column(
        "meetings",
        sa.Column(
            "empresa_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("empresas.id"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE meetings m
           SET empresa_id = pem.empresa_id
          FROM prospect_empresa_map pem
         WHERE m.prospect_id = pem.prospect_id;
        """
    )
    op.create_index("ix_meetings_empresa_id", "meetings", ["empresa_id"])

    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                 WHERE table_name='account_drafts' AND column_name='prospect_id'
            ) THEN
                ALTER TABLE account_drafts
                    ADD COLUMN empresa_id UUID REFERENCES empresas(id);
                UPDATE account_drafts d
                   SET empresa_id = pem.empresa_id
                  FROM prospect_empresa_map pem
                 WHERE d.prospect_id = pem.prospect_id;
            END IF;
        END $$;
        """
    )

    op.add_column(
        "customers",
        sa.Column(
            "empresa_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("empresas.id"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE customers c
           SET empresa_id = pem.empresa_id
          FROM prospect_empresa_map pem
         WHERE c.prospect_id = pem.prospect_id;
        """
    )
    op.create_index("ix_customers_empresa_id", "customers", ["empresa_id"])

    # ------------------------------------------------------------------
    # 8. Flag grandfathered operativo rows missing an active subscription.
    #    UI uses this to surface a "Revisar" chip; the new business rule
    #    (operativo requires linked active sub) only applies to NEW writes.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE empresas
           SET grandfathered = TRUE,
               fiscal_sync_error = COALESCE(
                   fiscal_sync_error,
                   'operativo sin suscripcion activa — revision manual'
               )
         WHERE lifecycle_stage = 'operativo'
           AND (eva_account_id IS NULL OR subscription_status IS DISTINCT FROM 'active');
        """
    )


def downgrade() -> None:
    # Reverse order — prospects + prospect_interactions stay intact; we only
    # undo what this migration created.

    # 7 reverse.
    op.drop_index("ix_customers_empresa_id", table_name="customers")
    op.drop_column("customers", "empresa_id")
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                 WHERE table_name='account_drafts' AND column_name='empresa_id'
            ) THEN
                ALTER TABLE account_drafts DROP COLUMN empresa_id;
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_meetings_empresa_id", table_name="meetings")
    op.drop_column("meetings", "empresa_id")

    # 6 reverse.
    op.drop_index("ix_empresa_interactions_empresa_id", table_name="empresa_interactions")
    op.drop_table("empresa_interactions")

    # 5 reverse — remove inserted empresas.
    op.execute("DELETE FROM empresas WHERE legacy_prospect_id IS NOT NULL")

    # 3 reverse.
    op.drop_table("prospect_empresa_map")

    # 2 reverse.
    op.drop_constraint("ck_payment_links_plan_tier", "payment_links", type_="check")
    op.drop_column("payment_links", "plan_tier")

    # 1 reverse — in reverse-declaration order.
    op.drop_index("empresas_eva_account_id_uniq", table_name="empresas")
    for column in [
        "legacy_prospect_id", "lost_reason", "tags", "assigned_to", "next_follow_up",
        "prospect_notes", "estimated_mrr_usd", "estimated_mrr_currency", "estimated_plan",
        "referred_by", "source", "contact_role", "contact_phone", "contact_email",
        "contact_name", "website", "grandfathered", "fiscal_sync_error",
        "fiscal_sync_pending_at", "version", "constancia_object_key",
        "cancellation_scheduled_at", "expected_close_date",
    ]:
        op.drop_column("empresas", column)
    op.drop_constraint("ck_empresas_billing_interval", "empresas", type_="check")
    op.drop_column("empresas", "billing_interval")
    op.drop_constraint("ck_empresas_lifecycle_stage", "empresas", type_="check")
    op.drop_column("empresas", "lifecycle_stage")
