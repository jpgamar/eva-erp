"""Mirror models for Eva production DB tables.

These use EvaBase so Alembic never targets them.
Column definitions mirror Eva's models exactly — no relationships
or constraints that would emit DDL.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.common.database import EvaBase


class EvaAccount(EvaBase):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_user_id = Column(String, nullable=False)
    account_type = Column(
        SQLEnum("COMMERCE", "PROPERTY_MANAGEMENT", name="account_type", create_type=False),
        nullable=False,
    )
    partner_id = Column(UUID(as_uuid=True), nullable=True)
    default_currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(64), nullable=True)

    # Billing
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(
        SQLEnum(
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "INCOMPLETE",
            "INCOMPLETE_EXPIRED",
            "TRIALING",
            "PAUSED",
            "UNPAID",
            name="subscription_status",
            create_type=False,
        ),
        nullable=True,
    )
    plan_tier = Column(
        SQLEnum("STARTER", "STANDARD", "PRO", name="plan_tier", create_type=False),
        nullable=True,
    )
    billing_interval = Column(
        SQLEnum("MONTHLY", "ANNUAL", name="billing_interval", create_type=False),
        nullable=True,
    )
    billing_currency = Column(String(3), nullable=False, default="MXN")
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    # Fiscal (CFDI)
    billing_legal_name = Column(String(255), nullable=True)
    billing_tax_id = Column(String(20), nullable=True)
    billing_tax_regime = Column(String(10), nullable=True)
    billing_postal_code = Column(String(10), nullable=True)
    billing_person_type = Column(
        SQLEnum(
            "PERSONA_FISICA",
            "PERSONA_MORAL",
            name="billing_person_type",
            create_type=False,
        ),
        nullable=True,
    )

    # Facturapi
    facturapi_org_api_key = Column(String(255), nullable=True)

    # Branding
    branding_logo_url = Column(String(512), nullable=True)

    # Add-ons
    addon_agents = Column(Integer, nullable=False, default=0)
    addon_seats = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaAccountUser(EvaBase):
    __tablename__ = "account_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    display_name = Column(String(255), nullable=True)
    role = Column(
        SQLEnum("OWNER", "ADMIN", "MEMBER", name="account_role", create_type=False),
        nullable=False,
        default="MEMBER",
    )
    status = Column(
        SQLEnum("ACTIVE", "INVITED", name="account_user_status", create_type=False),
        nullable=False,
        default="ACTIVE",
    )
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaPartner(EvaBase):
    __tablename__ = "partners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    brand_name = Column(String(255), nullable=True)
    logo_url = Column(String(2048), nullable=True)
    brand_icon_url = Column(String(2048), nullable=True)
    primary_color = Column(String(7), nullable=True)
    theme_json = Column(JSONB, nullable=True)
    custom_domain = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    type = Column(
        SQLEnum("WHITE_LABEL", "SOLUTIONS", name="partner_type", create_type=False),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaPartnerUser(EvaBase):
    __tablename__ = "partner_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(String, nullable=False)
    email = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    role = Column(
        SQLEnum("OWNER", "ADMIN", "MEMBER", name="partner_role", create_type=False),
        nullable=False,
        default="MEMBER",
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaPartnerDomain(EvaBase):
    __tablename__ = "partner_domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), nullable=False)
    host = Column(String(255), nullable=False, unique=True)
    normalized_host = Column(String(255), nullable=False, unique=True)
    status = Column(
        SQLEnum(
            "PENDING",
            "ACTIVE",
            "INACTIVE",
            name="partner_domain_status",
            create_type=False,
        ),
        nullable=False,
        default="PENDING",
    )
    is_primary = Column(Boolean, nullable=False, default=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaPartnerDeal(EvaBase):
    __tablename__ = "partner_deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), nullable=True)
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    stage = Column(
        SQLEnum(
            "to_contact",
            "contacted",
            "implementation",
            "won",
            "lost",
            name="partner_deal_stage",
            create_type=False,
        ),
        nullable=False,
        default="to_contact",
    )
    plan_tier = Column(String(50), nullable=False, default="Standard")
    billing_cycle = Column(String(20), nullable=False, default="monthly")
    won_at = Column(DateTime(timezone=True), nullable=True)
    lost_at = Column(DateTime(timezone=True), nullable=True)
    lost_reason = Column(String(255), nullable=True)
    linked_account_id = Column(UUID(as_uuid=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class EvaMonitoringIssue(EvaBase):
    __tablename__ = "admin_monitoring_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint = Column(String(255), nullable=False, unique=True)
    source = Column(String(80), nullable=False)
    category = Column(String(80), nullable=False)
    severity = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="open")
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    occurrences = Column(Integer, nullable=False, default=1)
    sample_payload = Column(JSONB, nullable=True)
    context_payload = Column(JSONB, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class EvaMonitoringCheck(EvaBase):
    __tablename__ = "admin_monitoring_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_key = Column(String(120), nullable=False)
    service = Column(String(80), nullable=False)
    target = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False)
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(String(500), nullable=True)
    details = Column(JSONB, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=False)
