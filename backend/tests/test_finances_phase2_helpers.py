from decimal import Decimal

import pytest

from fastapi import HTTPException

from src.finances.router import (
    _normalize_manual_deposit_reason,
    _normalize_manual_payment_reason,
    _resolve_period,
)
from src.finances.stripe_service import SUPPORTED_STRIPE_EVENT_TYPES, _to_decimal_amount, _to_upper_currency


def test_supported_stripe_event_types_cover_phase2_contract() -> None:
    assert {
        "payment_intent.succeeded",
        "charge.refunded",
        "payout.paid",
        "payout.failed",
    }.issubset(SUPPORTED_STRIPE_EVENT_TYPES)


def test_to_decimal_amount_handles_cents() -> None:
    assert _to_decimal_amount(12345) == Decimal("123.45")
    assert _to_decimal_amount(None) == Decimal("0.00")


def test_to_upper_currency_normalizes_values() -> None:
    assert _to_upper_currency("mxn") == "MXN"
    assert _to_upper_currency("usd") == "USD"
    assert _to_upper_currency("unknown") == "MXN"


def test_normalize_manual_payment_reason_validation() -> None:
    assert _normalize_manual_payment_reason("cash") == "cash"
    with pytest.raises(HTTPException):
        _normalize_manual_payment_reason("wire")


def test_normalize_manual_deposit_reason_validation() -> None:
    assert _normalize_manual_deposit_reason("manual_bank_deposit") == "manual_bank_deposit"
    with pytest.raises(HTTPException):
        _normalize_manual_deposit_reason("cash")


def test_resolve_period_default_and_custom() -> None:
    key, start, next_month = _resolve_period("2026-02")
    assert key == "2026-02"
    assert start.isoformat() == "2026-02-01"
    assert next_month.isoformat() == "2026-03-01"

    key_default, _, _ = _resolve_period(None)
    assert len(key_default) == 7
