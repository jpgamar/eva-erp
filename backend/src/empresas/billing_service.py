"""Stripe billing for Empresa custom deals."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.empresas.models import Empresa

logger = logging.getLogger(__name__)


def _ensure_stripe() -> None:
    if not settings.eva_stripe_secret_key:
        raise ValueError("EVA_STRIPE_SECRET_KEY not configured")
    stripe.api_key = settings.eva_stripe_secret_key


async def create_checkout_session(
    db: AsyncSession,
    empresa: Empresa,
    *,
    amount_mxn: Decimal,
    description: str,
    interval: str,
    recipient_email: str,
) -> str:
    """Create a Stripe Checkout Session for a recurring custom deal."""
    _ensure_stripe()

    amount_minor = int(amount_mxn * 100)
    if amount_minor <= 0:
        raise ValueError("Amount must be greater than zero")

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
            # DB failed — clean up the Stripe customer to avoid orphans
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

    session = stripe.checkout.Session.create(
        customer=customer_id,
        line_items=[
            {
                "price_data": {
                    "product_data": {"name": desc},
                    "currency": "mxn",
                    "unit_amount": amount_minor,
                    "recurring": {"interval": interval},
                },
                "quantity": 1,
            }
        ],
        mode="subscription",
        subscription_data={
            "metadata": {
                "source": "erp_custom_deal",
                "empresa_id": str(empresa.id),
                "description": desc,
            },
        },
        metadata={
            "empresa_id": str(empresa.id),
            "source": "erp_custom_deal",
        },
        payment_method_types=["card"],
        success_url=f"{settings.frontend_url}/empresas?payment=success",
        cancel_url=f"{settings.frontend_url}/empresas?payment=cancelled",
    )

    return session.url


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
