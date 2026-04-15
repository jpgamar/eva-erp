"""Stripe billing for Empresa custom deals — IVA-aware."""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.empresas.models import Empresa
from src.eva_billing.service import (
    IVA_RATE,
    ISR_RETENTION_RATE,
    IVA_RETENTION_RATE,
    _compute_quote,
    is_fiscal_complete,
    resolve_retention_applicable,
)

logger = logging.getLogger(__name__)


PlanTierLiteral = Literal["standard", "pro"]


def next_billing_cycle_anchor(payment_day: int, *, from_date: date | None = None) -> int:
    """Unix timestamp of the next occurrence of ``payment_day`` (1-31).

    Clamps to the last day of the target month when payment_day exceeds that
    month's length (e.g., ``payment_day=31`` in February → Feb 28/29).
    """
    if payment_day < 1 or payment_day > 31:
        raise ValueError("payment_day must be between 1 and 31")
    if from_date is None:
        from_date = date.today()

    target_year, target_month = from_date.year, from_date.month
    last_day = calendar.monthrange(target_year, target_month)[1]
    day = min(payment_day, last_day)
    candidate = date(target_year, target_month, day)
    if candidate <= from_date:
        target_month += 1
        if target_month == 13:
            target_month = 1
            target_year += 1
        last_day = calendar.monthrange(target_year, target_month)[1]
        day = min(payment_day, last_day)
        candidate = date(target_year, target_month, day)
    return int(datetime.combine(candidate, time.min).timestamp())


def _resolve_canonical_product(plan_tier: PlanTierLiteral, person_type: str | None) -> str | None:
    """Return the canonical Stripe Product ID for STANDARD/PRO × moral/fisica.

    Returns None when no canonical product is configured for this environment
    (e.g., before bootstrap has been run). Callers fall back to inline
    product_data in that case.
    """
    if plan_tier == "standard":
        if person_type == "moral":
            return settings.stripe_product_standard_moral_mxn or None
        return settings.stripe_product_standard_fisica_mxn or None
    if plan_tier == "pro":
        if person_type == "moral":
            return settings.stripe_product_pro_moral_mxn or None
        return settings.stripe_product_pro_fisica_mxn or None
    return None


def _ensure_stripe() -> None:
    if not settings.eva_stripe_secret_key:
        raise ValueError("EVA_STRIPE_SECRET_KEY not configured")
    stripe.api_key = settings.eva_stripe_secret_key


def preview_checkout(empresa: Empresa, *, amount_mxn: Decimal) -> dict:
    """Compute IVA/retention breakdown for a custom deal without creating anything.

    Returns the EvaBillingQuoteResponse dict plus retention_applicable flag.
    """
    retention = resolve_retention_applicable(empresa.person_type, empresa.regimen_fiscal)
    if retention is None:
        raise ValueError(
            "Define el tipo de persona (moral o fisica) antes de crear el link de cobro"
        )

    if retention and not is_fiscal_complete(
        empresa.rfc,
        empresa.razon_social,
        empresa.regimen_fiscal,
        empresa.fiscal_postal_code,
        empresa.cfdi_use,
        empresa.person_type,
    ):
        raise ValueError(
            "Completa la informacion fiscal antes de crear el link de cobro"
        )

    base_minor = int(amount_mxn * 100)
    if base_minor <= 0:
        raise ValueError("Amount must be greater than zero")

    if retention:
        # Persona moral: compute full quote with retentions
        quote = _compute_quote(base_minor, retention_applicable=True)
        return {
            "retention_applicable": True,
            "base_subtotal_minor": quote.base_subtotal_minor,
            "iva_minor": quote.iva_minor,
            "isr_retention_minor": quote.isr_retention_minor,
            "iva_retention_minor": quote.iva_retention_minor,
            "payable_total_minor": quote.payable_total_minor,
            "stripe_charges_tax": False,
        }
    else:
        # Persona fisica: base only, Stripe adds IVA via automatic_tax
        quote = _compute_quote(base_minor, retention_applicable=False)
        return {
            "retention_applicable": False,
            "base_subtotal_minor": base_minor,
            "iva_minor": quote.iva_minor,
            "isr_retention_minor": 0,
            "iva_retention_minor": 0,
            "payable_total_minor": quote.payable_total_minor,
            "stripe_charges_tax": True,
        }


async def create_checkout_session(
    db: AsyncSession,
    empresa: Empresa,
    *,
    amount_mxn: Decimal,
    description: str,
    interval: str,
    recipient_email: str,
    plan_tier: PlanTierLiteral = "standard",
) -> tuple[str, dict]:
    """Create a Stripe Checkout Session for a recurring custom deal.

    Returns (checkout_url, quote_dict).
    """
    _ensure_stripe()

    # Recompute quote server-side (never trust client values)
    quote = preview_checkout(empresa, amount_mxn=amount_mxn)

    desc = description or f"Servicio EvaAI — {empresa.name}"

    # Get or create Stripe Customer
    customer_id = empresa.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            name=empresa.razon_social or empresa.name,
            email=recipient_email,
            metadata={"empresa_id": str(empresa.id), "source": "erp_custom_deal"},
        )
        customer_id = customer.id
        empresa.stripe_customer_id = customer_id
        # Store recipient email at the same time
        current_recipients = empresa.billing_recipient_emails or []
        normalized = recipient_email.strip().lower()
        if normalized not in [e.lower() for e in current_recipients]:
            empresa.billing_recipient_emails = current_recipients + [normalized]
        db.add(empresa)
        try:
            await db.flush()
        except Exception:
            try:
                stripe.Customer.delete(customer_id)
            except Exception:
                pass
            raise
    else:
        # Customer exists — just ensure recipient email is tracked
        current_recipients = empresa.billing_recipient_emails or []
        normalized = recipient_email.strip().lower()
        if normalized not in [e.lower() for e in current_recipients]:
            empresa.billing_recipient_emails = current_recipients + [normalized]
            db.add(empresa)
            await db.flush()

    # Build Stripe session params based on persona type
    session_params: dict = {
        "customer": customer_id,
        "mode": "subscription",
        "subscription_data": {
            "metadata": {
                "source": "erp_custom_deal",
                "empresa_id": str(empresa.id),
                "description": desc,
                "base_subtotal_minor": str(quote["base_subtotal_minor"]),
                "retention_applicable": str(quote["retention_applicable"]),
            },
        },
        "metadata": {
            "empresa_id": str(empresa.id),
            "source": "erp_custom_deal",
        },
        "payment_method_types": ["card"],
        "success_url": f"{settings.frontend_url}/empresas?payment=success",
        "cancel_url": f"{settings.frontend_url}/empresas?payment=cancelled",
    }

    canonical_product_id = _resolve_canonical_product(plan_tier, empresa.person_type)

    def _build_price_data(unit_amount: int) -> dict:
        base = {
            "currency": "mxn",
            "unit_amount": unit_amount,
            "recurring": {"interval": interval},
        }
        if canonical_product_id:
            # Reuse the stable canonical Product across customers — prevents
            # the Stripe Product list from filling with one-off rows.
            base["product"] = canonical_product_id
        else:
            # No canonical Product configured for this env — fall back to
            # inline product_data so checkout still works during bootstrap.
            base["product_data"] = {"name": desc}
        return base

    if quote["retention_applicable"]:
        # Persona moral: charge post-retention total (IVA baked in, retentions subtracted)
        session_params["line_items"] = [
            {"price_data": _build_price_data(quote["payable_total_minor"]), "quantity": 1}
        ]
    else:
        # Persona fisica: charge base amount, Stripe adds IVA via automatic_tax
        session_params["line_items"] = [
            {"price_data": _build_price_data(quote["base_subtotal_minor"]), "quantity": 1}
        ]
        session_params["automatic_tax"] = {"enabled": True}
        session_params["billing_address_collection"] = "auto"
        session_params["customer_update"] = {"name": "auto", "address": "auto"}

    # Anchor subscription billing to the operator-specified payment_day when
    # available. Stripe charges the full amount immediately at checkout; the
    # anchor controls subsequent recurring billing.
    if empresa.payment_day:
        try:
            anchor_ts = next_billing_cycle_anchor(empresa.payment_day)
            session_params["subscription_data"]["billing_cycle_anchor"] = anchor_ts
            # Prorate the first partial period so the operator isn't double-charged.
            session_params["subscription_data"]["proration_behavior"] = "create_prorations"
        except ValueError:
            logger.warning(
                "empresas.checkout.invalid_payment_day empresa=%s payment_day=%s",
                empresa.id, empresa.payment_day,
            )

    session_params["subscription_data"]["metadata"]["plan_tier"] = plan_tier

    session = stripe.checkout.Session.create(**session_params)
    return session.url, quote


async def create_portal_session(empresa: Empresa) -> str:
    """Create a Stripe Customer Portal session for subscription management."""
    _ensure_stripe()

    if not empresa.stripe_customer_id:
        raise ValueError("Empresa does not have a Stripe customer")

    session = stripe.billing_portal.Session.create(
        customer=empresa.stripe_customer_id,
        return_url=f"{settings.frontend_url}/empresas",
    )
    return session.url
