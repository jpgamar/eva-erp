"""add proveedores, pagos_proveedor, facturas_proveedor, diferencias_cambiarias

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "l1m2n3o4p5q6"
down_revision = "k0l1m2n3o4p5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Proveedores
    op.create_table(
        "proveedores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("bank_account", sa.String(20), nullable=True),
        sa.Column("default_currency", sa.String(3), server_default="USD"),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Facturas Proveedor (must come before pagos because of FK in pago_aplicaciones)
    op.create_table(
        "facturas_proveedor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("proveedor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proveedores.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_total_mxn", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="pendiente"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_amount", sa.Numeric(18, 2), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.String(512), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Pagos Proveedor (unified: anticipo + pago directo)
    op.create_table(
        "pagos_proveedor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("proveedor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proveedores.id"), nullable=False),
        sa.Column("tipo", sa.String(20), server_default="anticipo"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_amount_mxn", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(30), server_default="transferencia"),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="pendiente"),
        sa.Column("applied_amount", sa.Numeric(18, 2), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Pago Aplicaciones (junction: pago → factura)
    op.create_table(
        "pago_aplicaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pago_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pagos_proveedor.id"), nullable=False),
        sa.Column("factura_proveedor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("facturas_proveedor.id"), nullable=False),
        sa.Column("applied_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("pago_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("document_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_amount_at_pago_rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("base_amount_at_document_rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("exchange_difference_mxn", sa.Numeric(18, 2), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Diferencias Cambiarias
    op.create_table(
        "diferencias_cambiarias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proveedor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proveedores.id"), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("foreign_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("original_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("settlement_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("gain_loss_mxn", sa.Numeric(18, 2), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add exchange_rate column to existing financial tables
    op.add_column("exchange_rates", sa.Column("rate_type", sa.String(20), server_default="FIX"))


def downgrade() -> None:
    op.drop_column("exchange_rates", "rate_type")
    op.drop_table("diferencias_cambiarias")
    op.drop_table("pago_aplicaciones")
    op.drop_table("pagos_proveedor")
    op.drop_table("facturas_proveedor")
    op.drop_table("proveedores")
