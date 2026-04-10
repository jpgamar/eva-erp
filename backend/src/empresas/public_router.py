"""Public (unauthenticated) payment link endpoints."""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from src.common.config import settings
from src.common.database import async_sessionmaker, engine
from src.empresas.models import Empresa, PaymentLink
from src.empresas.schemas import PaymentLinkPublicResponse, PreviewCheckoutResponse
from src.eva_billing.service import _compute_quote, resolve_retention_applicable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/pay", tags=["public-pay"])


async def _get_link_and_empresa(token: str) -> tuple:
    """Load PaymentLink + Empresa in a fresh session. Returns (link, empresa, db)."""
    db = async_sessionmaker(engine)()
    result = await db.execute(
        select(PaymentLink).where(PaymentLink.token == token)
    )
    link = result.scalar_one_or_none()
    if not link:
        await db.close()
        raise HTTPException(status_code=404, detail="Payment link not found")

    empresa = await db.get(Empresa, link.empresa_id)
    if not empresa:
        await db.close()
        raise HTTPException(status_code=404, detail="Empresa not found")

    return link, empresa, db


@router.get("/{token}", response_model=PaymentLinkPublicResponse)
async def get_payment_link(token: str):
    """Public endpoint: get payment link details for the landing page."""
    link, empresa, db = await _get_link_and_empresa(token)
    try:
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
    finally:
        await db.close()


@router.post("/{token}/checkout")
async def create_checkout_for_link(token: str):
    """Public endpoint: create a Stripe Checkout Session on-demand for this payment link."""
    link, empresa, db = await _get_link_and_empresa(token)
    try:
        if link.status != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Este link de pago ya no esta activo (estado: {link.status})",
            )

        if not settings.eva_stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe not configured")
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

        session = stripe.checkout.Session.create(**session_params)

        link.stripe_checkout_session_id = session.id
        db.add(link)
        await db.commit()

        return {"checkout_url": session.url}

    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Failed to create checkout for payment link %s", token)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await db.close()
