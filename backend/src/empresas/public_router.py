"""Public (unauthenticated) payment link endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from src.common.config import settings
from src.common.database import async_sessionmaker, engine
from src.empresas.models import Empresa, PaymentLink
from src.empresas.schemas import PaymentLinkPublicResponse, PreviewCheckoutResponse
from src.eva_billing.service import _compute_quote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/pay", tags=["public-pay"])


@router.get("/{token}", response_model=PaymentLinkPublicResponse)
async def get_payment_link(token: str):
    """Public endpoint: get payment link details for the landing page."""
    async with async_sessionmaker(engine)() as db:
        link = await _load_link(db, token)
        empresa = await db.get(Empresa, link.empresa_id)
        if not empresa:
            raise HTTPException(status_code=404, detail="Payment link not found")

        _check_expiry(link)

        quote = _compute_quote(link.amount_minor, retention_applicable=link.retention_applicable)
        return PaymentLinkPublicResponse(
            empresa_name=empresa.name,
            description=link.description,
            amount_minor=link.amount_minor,
            currency=link.currency,
            interval=link.interval,
            retention_applicable=link.retention_applicable,
            status=link.status,
            quote=PreviewCheckoutResponse(
                retention_applicable=quote.retention_applicable,
                base_subtotal_minor=quote.base_subtotal_minor,
                iva_minor=quote.iva_minor,
                isr_retention_minor=quote.isr_retention_minor,
                iva_retention_minor=quote.iva_retention_minor,
                payable_total_minor=quote.payable_total_minor,
                stripe_charges_tax=not link.retention_applicable,
            ),
        )


@router.post("/{token}/checkout")
async def create_checkout_for_link(token: str):
    """Public endpoint: create a Stripe Checkout Session on-demand."""
    async with async_sessionmaker(engine)() as db:
        link = await _load_link(db, token)
        empresa = await db.get(Empresa, link.empresa_id)
        if not empresa:
            raise HTTPException(status_code=404, detail="Payment link not found")

        _check_expiry(link)

        if link.status != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Este link de pago ya no esta activo (estado: {link.status})",
            )

        if not settings.eva_stripe_secret_key:
            raise HTTPException(status_code=503, detail="Payment service unavailable")
        stripe.api_key = settings.eva_stripe_secret_key

        # Get or reuse Stripe customer
        customer_id = empresa.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                name=empresa.razon_social or empresa.name,
                email=link.recipient_email,
                metadata={"empresa_id": str(empresa.id), "source": "erp_custom_deal"},
            )
            customer_id = customer.id
            empresa.stripe_customer_id = customer_id
            db.add(empresa)
            await db.flush()

        base_url = settings.eva_app_base_url.rstrip("/")
        desc = link.description or f"Servicio EvaAI — {empresa.name}"

        session_params: dict = {
            "customer": customer_id,
            "mode": "subscription",
            "subscription_data": {
                "metadata": {
                    "source": "erp_custom_deal",
                    "empresa_id": str(empresa.id),
                    "description": desc,
                    "base_subtotal_minor": str(link.amount_minor),
                    "retention_applicable": str(link.retention_applicable),
                    "payment_link_token": link.token,
                },
            },
            "metadata": {
                "empresa_id": str(empresa.id),
                "source": "erp_custom_deal",
                "payment_link_token": link.token,
            },
            "payment_method_types": ["card"],
            "success_url": f"{base_url}/pay/{link.token}?status=success",
            "cancel_url": f"{base_url}/pay/{link.token}?status=cancelled",
        }

        if link.retention_applicable:
            quote = _compute_quote(link.amount_minor, retention_applicable=True)
            session_params["line_items"] = [
                {
                    "price_data": {
                        "product_data": {"name": desc},
                        "currency": "mxn",
                        "unit_amount": quote.payable_total_minor,
                        "recurring": {"interval": link.interval},
                    },
                    "quantity": 1,
                }
            ]
        else:
            session_params["line_items"] = [
                {
                    "price_data": {
                        "product_data": {"name": desc},
                        "currency": "mxn",
                        "unit_amount": link.amount_minor,
                        "recurring": {"interval": link.interval},
                    },
                    "quantity": 1,
                }
            ]
            session_params["automatic_tax"] = {"enabled": True}
            session_params["billing_address_collection"] = "auto"
            session_params["customer_update"] = {"name": "auto", "address": "auto"}

        try:
            session = stripe.checkout.Session.create(**session_params)
        except stripe.error.StripeError as exc:
            logger.exception("Stripe error for payment link %s", token)
            raise HTTPException(status_code=502, detail="Payment processing failed") from exc

        link.stripe_checkout_session_id = session.id
        db.add(link)
        await db.commit()

        return {"checkout_url": session.url}


async def _load_link(db, token: str) -> PaymentLink:
    """Load a PaymentLink by token, raise 404 if not found."""
    result = await db.execute(
        select(PaymentLink).where(PaymentLink.token == token)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")
    return link


def _check_expiry(link: PaymentLink) -> None:
    """Raise 410 if the link has expired."""
    if link.expires_at and datetime.now(timezone.utc) > link.expires_at:
        raise HTTPException(status_code=410, detail="Este link de pago ha expirado")
