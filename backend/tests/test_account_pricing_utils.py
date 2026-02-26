import pytest

from fastapi import HTTPException

from src.eva_platform.pricing_models import AccountPricingProfile
from src.eva_platform.router.accounts import (
    _normalize_billing_currency,
    _normalize_billing_interval,
    _pricing_complete,
)


def test_normalize_billing_currency_accepts_mxn_and_usd() -> None:
    assert _normalize_billing_currency("mxn") == "MXN"
    assert _normalize_billing_currency("USD") == "USD"


def test_normalize_billing_currency_rejects_invalid_value() -> None:
    with pytest.raises(HTTPException) as exc:
        _normalize_billing_currency("eur")
    assert exc.value.status_code == 422


def test_normalize_billing_interval_accepts_aliases() -> None:
    assert _normalize_billing_interval("monthly") == "MONTHLY"
    assert _normalize_billing_interval("yearly") == "ANNUAL"


def test_normalize_billing_interval_rejects_invalid_value() -> None:
    with pytest.raises(HTTPException) as exc:
        _normalize_billing_interval("weekly")
    assert exc.value.status_code == 422


def test_pricing_complete_checks_required_fields() -> None:
    assert _pricing_complete(None) is False

    non_billable = AccountPricingProfile(is_billable=False)
    assert _pricing_complete(non_billable) is True

    incomplete = AccountPricingProfile(
        is_billable=True,
        billing_amount=None,
        billing_currency="MXN",
        billing_interval="MONTHLY",
    )
    assert _pricing_complete(incomplete) is False

    complete = AccountPricingProfile(
        is_billable=True,
        billing_amount=100,
        billing_currency="MXN",
        billing_interval="MONTHLY",
    )
    assert _pricing_complete(complete) is True
