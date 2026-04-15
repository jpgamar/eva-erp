"""Tests for Phase 4 Stripe delegation helpers."""

from __future__ import annotations

from datetime import date

import pytest

from src.empresas.billing_service import (
    _resolve_canonical_product,
    next_billing_cycle_anchor,
)


class TestBillingCycleAnchor:
    def test_payment_day_15_future_in_current_month(self):
        anchor = next_billing_cycle_anchor(15, from_date=date(2026, 5, 1))
        # Expected: 2026-05-15 00:00:00 local.
        from datetime import datetime
        assert datetime.fromtimestamp(anchor).date() == date(2026, 5, 15)

    def test_payment_day_1_already_past_rolls_to_next_month(self):
        anchor = next_billing_cycle_anchor(1, from_date=date(2026, 5, 5))
        from datetime import datetime
        assert datetime.fromtimestamp(anchor).date() == date(2026, 6, 1)

    def test_payment_day_31_in_feb_clamps_to_last_day(self):
        anchor = next_billing_cycle_anchor(31, from_date=date(2026, 2, 1))
        from datetime import datetime
        # 2026 is not a leap year, so Feb has 28 days.
        assert datetime.fromtimestamp(anchor).date() == date(2026, 2, 28)

    def test_payment_day_31_in_feb_2028_leap_year(self):
        anchor = next_billing_cycle_anchor(31, from_date=date(2028, 2, 1))
        from datetime import datetime
        assert datetime.fromtimestamp(anchor).date() == date(2028, 2, 29)

    def test_invalid_payment_day_raises(self):
        with pytest.raises(ValueError):
            next_billing_cycle_anchor(0)
        with pytest.raises(ValueError):
            next_billing_cycle_anchor(32)

    def test_payment_day_equals_today_rolls_to_next_month(self):
        anchor = next_billing_cycle_anchor(15, from_date=date(2026, 5, 15))
        from datetime import datetime
        # Today is the payment_day → roll to next month.
        assert datetime.fromtimestamp(anchor).date() == date(2026, 6, 15)


class TestResolveCanonicalProduct:
    def test_standard_moral_maps_to_env_var(self, monkeypatch):
        monkeypatch.setattr("src.empresas.billing_service.settings.stripe_product_standard_moral_mxn", "prod_std_moral")
        assert _resolve_canonical_product("standard", "moral") == "prod_std_moral"

    def test_standard_fisica_maps_to_env_var(self, monkeypatch):
        monkeypatch.setattr("src.empresas.billing_service.settings.stripe_product_standard_fisica_mxn", "prod_std_fisica")
        assert _resolve_canonical_product("standard", "fisica") == "prod_std_fisica"

    def test_pro_moral_maps_to_env_var(self, monkeypatch):
        monkeypatch.setattr("src.empresas.billing_service.settings.stripe_product_pro_moral_mxn", "prod_pro_moral")
        assert _resolve_canonical_product("pro", "moral") == "prod_pro_moral"

    def test_unknown_tier_returns_none(self, monkeypatch):
        assert _resolve_canonical_product("rents_20", "moral") is None  # type: ignore[arg-type]

    def test_unset_env_returns_none(self, monkeypatch):
        monkeypatch.setattr("src.empresas.billing_service.settings.stripe_product_standard_moral_mxn", "")
        assert _resolve_canonical_product("standard", "moral") is None
