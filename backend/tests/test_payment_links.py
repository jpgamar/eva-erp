"""Tests for PaymentLink model and public API logic."""

from __future__ import annotations

import secrets
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.eva_billing.service import _compute_quote


class TestPaymentLinkToken:
    def test_token_is_url_safe(self):
        token = secrets.token_urlsafe(9)
        assert len(token) == 12
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_tokens_are_unique(self):
        tokens = {secrets.token_urlsafe(9) for _ in range(1000)}
        assert len(tokens) == 1000  # No collisions in 1000 tokens


class TestPaymentLinkQuotePreview:
    def test_persona_moral_quote_for_payment_page(self):
        """Payment page should show same breakdown as checkout modal."""
        quote = _compute_quote(200_000, retention_applicable=True)
        assert quote.base_subtotal_minor == 200_000
        assert quote.iva_minor == 32_000
        assert quote.isr_retention_minor == 2_500
        assert quote.iva_retention_minor == 21_333
        assert quote.payable_total_minor == 208_167

    def test_persona_fisica_quote_for_payment_page(self):
        """Payment page shows base + note about Stripe IVA."""
        quote = _compute_quote(200_000, retention_applicable=False)
        assert quote.base_subtotal_minor == 200_000
        assert quote.iva_minor == 32_000
        assert quote.isr_retention_minor == 0
        assert quote.iva_retention_minor == 0
        assert quote.payable_total_minor == 232_000


class TestPaymentLinkModel:
    def test_model_fields(self):
        from src.empresas.models import PaymentLink
        # Verify the model has all required columns
        columns = {c.name for c in PaymentLink.__table__.columns}
        expected = {
            "id", "token", "empresa_id", "amount_minor", "currency",
            "description", "interval", "recipient_email", "retention_applicable",
            "status", "created_by", "created_at", "expires_at", "paid_at",
            "stripe_checkout_session_id",
        }
        assert expected.issubset(columns)

    def test_token_column_is_unique(self):
        from src.empresas.models import PaymentLink
        token_col = PaymentLink.__table__.columns["token"]
        assert token_col.unique is True

    def test_default_status_is_active(self):
        from src.empresas.models import PaymentLink
        status_col = PaymentLink.__table__.columns["status"]
        assert status_col.server_default.arg == "active"


class TestPublicPaymentLinkResponse:
    def test_schema_includes_quote(self):
        from src.empresas.schemas import PaymentLinkPublicResponse, PreviewCheckoutResponse
        # Verify the response schema can be constructed
        response = PaymentLinkPublicResponse(
            empresa_name="Test Corp",
            description="Servicio EvaAI",
            amount_minor=200_000,
            currency="MXN",
            interval="month",
            retention_applicable=True,
            status="active",
            quote=PreviewCheckoutResponse(
                retention_applicable=True,
                base_subtotal_minor=200_000,
                iva_minor=32_000,
                isr_retention_minor=2_500,
                iva_retention_minor=21_333,
                payable_total_minor=208_167,
                stripe_charges_tax=False,
            ),
        )
        assert response.empresa_name == "Test Corp"
        assert response.quote.payable_total_minor == 208_167
        assert response.status == "active"
