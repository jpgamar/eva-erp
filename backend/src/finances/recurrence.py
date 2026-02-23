from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from src.finances.schemas import IncomeRecurrenceType

ALLOWED_RECURRENCE_TYPES: set[str] = {"monthly", "one_time", "custom"}
DEFAULT_CUSTOM_INTERVAL_MONTHS = 1


def extract_income_recurrence(metadata_json: dict | None, is_recurring: bool) -> tuple[IncomeRecurrenceType, int | None]:
    metadata = metadata_json if isinstance(metadata_json, dict) else {}

    raw_type = str(metadata.get("recurrence_type") or "").strip().lower()
    if raw_type not in ALLOWED_RECURRENCE_TYPES:
        raw_type = "monthly" if is_recurring else "one_time"
    recurrence_type = cast(IncomeRecurrenceType, raw_type)

    interval: int | None = None
    if recurrence_type == "custom":
        try:
            interval = int(metadata.get("custom_interval_months"))
        except (TypeError, ValueError):
            interval = DEFAULT_CUSTOM_INTERVAL_MONTHS
        if interval < 1:
            interval = DEFAULT_CUSTOM_INTERVAL_MONTHS

    return recurrence_type, interval


def normalize_income_recurrence_payload(
    *,
    recurrence_type: str | None,
    custom_interval_months: int | None,
    is_recurring: bool | None,
    existing_metadata: dict | None = None,
    existing_is_recurring: bool | None = None,
) -> tuple[IncomeRecurrenceType, int | None, bool]:
    if recurrence_type is not None:
        chosen_type = recurrence_type.strip().lower()
    elif is_recurring is not None:
        chosen_type = "monthly" if is_recurring else "one_time"
    elif existing_is_recurring is not None:
        chosen_type, _ = extract_income_recurrence(existing_metadata, existing_is_recurring)
    else:
        chosen_type = "one_time"

    if chosen_type not in ALLOWED_RECURRENCE_TYPES:
        raise ValueError(f"Invalid recurrence_type: {chosen_type}")

    existing_type, existing_interval = extract_income_recurrence(existing_metadata, bool(existing_is_recurring))
    interval: int | None = None
    if chosen_type == "custom":
        interval = custom_interval_months
        if interval is None and existing_type == "custom":
            interval = existing_interval
        if interval is None:
            interval = DEFAULT_CUSTOM_INTERVAL_MONTHS
        if interval < 1:
            raise ValueError("custom_interval_months must be >= 1")

    normalized = cast(IncomeRecurrenceType, chosen_type)
    return normalized, interval, normalized != "one_time"


def build_income_metadata(
    existing_metadata: dict | None,
    recurrence_type: IncomeRecurrenceType,
    custom_interval_months: int | None,
) -> dict:
    metadata = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
    metadata["recurrence_type"] = recurrence_type
    if recurrence_type == "custom":
        metadata["custom_interval_months"] = int(custom_interval_months or DEFAULT_CUSTOM_INTERVAL_MONTHS)
    else:
        metadata.pop("custom_interval_months", None)
    return metadata


def income_monthly_mrr_equivalent(
    amount_usd: Decimal,
    recurrence_type: IncomeRecurrenceType,
    custom_interval_months: int | None,
) -> Decimal:
    return income_monthly_equivalent(amount_usd, recurrence_type, custom_interval_months)


def income_monthly_equivalent(
    amount: Decimal,
    recurrence_type: IncomeRecurrenceType,
    custom_interval_months: int | None,
) -> Decimal:
    if recurrence_type == "one_time":
        return Decimal("0.00")
    if recurrence_type == "custom":
        months = int(custom_interval_months or DEFAULT_CUSTOM_INTERVAL_MONTHS)
        if months < 1:
            months = DEFAULT_CUSTOM_INTERVAL_MONTHS
        return (amount / Decimal(months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
