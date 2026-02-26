from decimal import Decimal
from datetime import datetime, timezone

import pytest

from fastapi import HTTPException

from src.finances.models import StripePaymentEvent
from src.finances.router import (
    _income_key_for_payment_event,
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


def test_income_key_for_payment_event_handles_payment_intent_and_refund() -> None:
    now = datetime.now(timezone.utc)
    payment_event = StripePaymentEvent(
        stripe_event_id="evt_1",
        stripe_event_type="payment_intent.succeeded",
        stripe_payment_intent_id="pi_1",
        amount=Decimal("10.00"),
        currency="MXN",
        occurred_at=now,
        unlinked=True,
        source="webhook",
        processing_status="processed",
    )
    refund_event = StripePaymentEvent(
        stripe_event_id="evt_2",
        stripe_event_type="charge.refunded",
        stripe_charge_id="ch_1",
        amount=Decimal("-5.00"),
        currency="MXN",
        occurred_at=now,
        unlinked=True,
        source="webhook",
        processing_status="processed",
    )

    assert _income_key_for_payment_event(payment_event) == "pi:pi_1"
    assert _income_key_for_payment_event(refund_event) == "refund:ch_1"
