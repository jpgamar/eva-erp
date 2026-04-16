"""Unit tests for maybe_reprice_subscription_for_zip_change (Step B.7).

Feature-flagged: when an operator changes an empresa's fiscal_postal_code
and the new ZIP produces a different payable total than the old one, we
auto-create a new Stripe Price + swap the subscription item so the next
invoice bills the corrected amount.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.empresas.billing_service import maybe_reprice_subscription_for_zip_change


def _make_empresa(**kw) -> MagicMock:
    e = MagicMock()
    e.id = kw.get("id", "uuid-1")
    e.name = kw.get("name", "Test Empresa")
    e.person_type = kw.get("person_type", "persona_moral")
    e.regimen_fiscal = kw.get("regimen_fiscal", "601")
    e.monthly_amount = kw.get("monthly_amount", Decimal("1500.00"))
    e.fiscal_postal_code = kw.get("fiscal_postal_code", "37160")
    e.stripe_customer_id = kw.get("stripe_customer_id", "cus_X")
    e.stripe_subscription_id = kw.get("stripe_subscription_id", "sub_X")
    e.subscription_status = kw.get("subscription_status", "active")
    return e


class TestAutoRepriceSkipConditions:
    """Cases where the helper MUST skip — regardless of the feature flag."""

    @pytest.mark.asyncio
    async def test_skip_when_flag_off(self):
        emp = _make_empresa()
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = False
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="37160"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_no_subscription(self):
        emp = _make_empresa(stripe_subscription_id=None)
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = True
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="37160"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_sub_not_active(self):
        emp = _make_empresa(subscription_status="canceled")
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = True
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="37160"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_same_zip(self):
        emp = _make_empresa()
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = True
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="37160", new_zip="37160"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_payable_unchanged(self):
        """Both ZIPs are non-cedular → same payable → skip."""
        emp = _make_empresa()
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = True
            # CDMX → Jalisco — neither has cedular → payable unchanged.
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="44100"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_zero_monthly_amount(self):
        emp = _make_empresa(monthly_amount=Decimal("0"))
        with patch("src.empresas.billing_service.settings") as s:
            s.enable_cedular_auto_reprice = True
            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="37160"
            )
            assert result is None


class TestAutoRepriceHappyPath:
    """When ZIP move changes the payable, create Price + swap item."""

    @pytest.mark.asyncio
    async def test_gto_to_cdmx_triggers_reprice(self):
        """Empresa moves OUT of GTO → cedular drops off → payable goes UP."""
        emp = _make_empresa(fiscal_postal_code="06600")
        new_price = MagicMock(id="price_NEW")
        fake_sub = {"items": {"data": [{"id": "si_X"}]}}

        with patch("src.empresas.billing_service.settings") as s, \
             patch("src.empresas.billing_service.stripe") as stripe_mock, \
             patch("src.empresas.billing_service._ensure_stripe"):
            s.enable_cedular_auto_reprice = True
            s.stripe_product_standard_moral_mxn = "prod_standard_moral"
            stripe_mock.Price.create.return_value = new_price
            stripe_mock.Subscription.retrieve.return_value = fake_sub
            stripe_mock.SubscriptionItem.modify = MagicMock()

            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="37160", new_zip="06600"
            )

            assert result is not None
            assert result["new_stripe_price_id"] == "price_NEW"
            assert result["cedular_state_code"] is None  # CDMX — no cedular
            # Payable went UP by $30 because cedular drops off.
            assert result["new_payable_minor"] - result["old_payable_minor"] == 3000
            stripe_mock.SubscriptionItem.modify.assert_called_once_with(
                "si_X", price="price_NEW", proration_behavior="none"
            )

    @pytest.mark.asyncio
    async def test_cdmx_to_gto_triggers_reprice(self):
        """Empresa moves INTO GTO → cedular kicks in → payable goes DOWN."""
        emp = _make_empresa(fiscal_postal_code="37160")
        new_price = MagicMock(id="price_NEW_GTO")
        fake_sub = {"items": {"data": [{"id": "si_X"}]}}

        with patch("src.empresas.billing_service.settings") as s, \
             patch("src.empresas.billing_service.stripe") as stripe_mock, \
             patch("src.empresas.billing_service._ensure_stripe"):
            s.enable_cedular_auto_reprice = True
            s.stripe_product_standard_moral_mxn = "prod_standard_moral"
            stripe_mock.Price.create.return_value = new_price
            stripe_mock.Subscription.retrieve.return_value = fake_sub
            stripe_mock.SubscriptionItem.modify = MagicMock()

            result = await maybe_reprice_subscription_for_zip_change(
                emp, old_zip="06600", new_zip="37160"
            )

            assert result is not None
            assert result["cedular_state_code"] == "GTO"
            # Payable went DOWN by $30.
            assert result["old_payable_minor"] - result["new_payable_minor"] == 3000
