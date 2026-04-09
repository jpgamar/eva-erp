"""Stripe billing for Empresa custom deals — IVA-aware."""

from __future__ import annotations

import logging
from decimal import Decimal
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

    if quote["retention_applicable"]:
        # Persona moral: charge post-retention total (IVA baked in, retentions subtracted)
        session_params["line_items"] = [
            {
                "price_data": {
                    "product_data": {"name": desc},
                    "currency": "mxn",
                    "unit_amount": quote["payable_total_minor"],
                    "recurring": {"interval": interval},
                },
                "quantity": 1,
            }
        ]
    else:
        # Persona fisica: charge base amount, Stripe adds IVA via automatic_tax
        session_params["line_items"] = [
            {
                "price_data": {
                    "product_data": {"name": desc},
                    "currency": "mxn",
                    "unit_amount": quote["base_subtotal_minor"],
                    "recurring": {"interval": interval},
                },
                "quantity": 1,
            }
        ]
        session_params["automatic_tax"] = {"enabled": True}
        session_params["billing_address_collection"] = "auto"
        session_params["customer_update"] = {"name": "auto", "address": "auto"}

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
