from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import settings
from src.common.database import async_session
from src.customers.models import Customer
from src.finances.models import ExchangeRate, IncomeEntry, StripePaymentEvent, StripePayoutEvent
from src.finances.recurrence import build_income_metadata

logger = logging.getLogger(__name__)

SUPPORTED_STRIPE_EVENT_TYPES: set[str] = {
    "payment_intent.succeeded",
    "charge.refunded",
    "payout.paid",
    "payout.failed",
}

PAYMENT_EVENT_TYPES: set[str] = {
    "payment_intent.succeeded",
    "charge.refunded",
}

PAYOUT_EVENT_TYPES: set[str] = {
    "payout.paid",
    "payout.failed",
}

DEFAULT_MXN_TO_USD = Decimal("0.05")


def _to_decimal_amount(value: Any) -> Decimal:
    try:
        cents = int(value)
    except (TypeError, ValueError):
        cents = 0
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))


def _to_datetime(value: Any) -> datetime:
    try:
        ts = int(value)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


def _to_upper_currency(value: Any) -> str:
    raw = str(value or "MXN").strip().upper()
    return raw if len(raw) == 3 else "MXN"


def _parse_uuid(value: Any) -> uuid.UUID | None:
    try:
        if value is None:
            return None
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _extract_metadata(data_object: dict[str, Any]) -> dict[str, Any]:
    metadata = data_object.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _resolve_account_id_from_metadata(metadata: dict[str, Any]) -> uuid.UUID | None:
    for key in ("account_id", "eva_account_id", "erp_account_id"):
        parsed = _parse_uuid(metadata.get(key))
        if parsed is not None:
            return parsed
    return None


async def _resolve_links(
    db: AsyncSession,
    *,
    stripe_customer_id: str | None,
    metadata: dict[str, Any],
) -> tuple[uuid.UUID | None, uuid.UUID | None, bool]:
    account_id = _resolve_account_id_from_metadata(metadata)
    customer_id: uuid.UUID | None = None

    normalized_customer_id = str(stripe_customer_id).strip() if stripe_customer_id else ""
    if normalized_customer_id:
        customer_result = await db.execute(
            select(Customer.id).where(Customer.stripe_customer_id == normalized_customer_id)
        )
        customer_id = customer_result.scalar_one_or_none()

    unlinked = account_id is None
    return customer_id, account_id, unlinked


async def _get_mxn_to_usd(db: AsyncSession) -> Decimal:
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.from_currency == "USD", ExchangeRate.to_currency == "MXN")
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if rate and rate.rate > 0:
        return round(Decimal("1") / rate.rate, 6)
    return DEFAULT_MXN_TO_USD


def _to_usd(amount: Decimal, currency: str, mxn_to_usd: Decimal) -> Decimal:
    if currency == "USD":
        return amount
    return (amount * mxn_to_usd).quantize(Decimal("0.01"))


def verify_and_parse_webhook(payload: bytes, signature: str | None) -> dict[str, Any]:
    webhook_secret = settings.eva_stripe_webhook_secret.strip()
    if not webhook_secret:
        raise ValueError("Stripe webhook secret is not configured")
    if not signature:
        raise ValueError("Stripe signature header is missing")

    event = stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=webhook_secret,
    )

    if hasattr(event, "to_dict_recursive"):
        return event.to_dict_recursive()
    return dict(event)


async def apply_stripe_event(
    db: AsyncSession,
    event: dict[str, Any],
    *,
    source: str = "webhook",
) -> str:
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id:
        return "ignored"
    if event_type not in SUPPORTED_STRIPE_EVENT_TYPES:
        return "ignored"

    if event_type in PAYMENT_EVENT_TYPES:
        existing = await db.execute(
            select(StripePaymentEvent.id).where(StripePaymentEvent.stripe_event_id == event_id)
        )
        if existing.scalar_one_or_none() is not None:
            return "duplicate"
        return await _process_payment_event(db, event=event, source=source)

    existing = await db.execute(
        select(StripePayoutEvent.id).where(StripePayoutEvent.stripe_event_id == event_id)
    )
    if existing.scalar_one_or_none() is not None:
        return "duplicate"
    return await _process_payout_event(db, event=event, source=source)


async def _process_payment_event(db: AsyncSession, *, event: dict[str, Any], source: str) -> str:
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    event_created_at = _to_datetime(event.get("created"))

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    metadata = _extract_metadata(obj)

    stripe_payment_intent_id = None
    stripe_charge_id = None
    stripe_refund_id = None
    stripe_customer_id = str(obj.get("customer")) if obj.get("customer") else None
    amount = Decimal("0")

    if event_type == "payment_intent.succeeded":
        stripe_payment_intent_id = str(obj.get("id") or "") or None
        latest_charge = obj.get("latest_charge")
        stripe_charge_id = str(latest_charge) if latest_charge else None
        amount = _to_decimal_amount(obj.get("amount_received") or obj.get("amount"))
    elif event_type == "charge.refunded":
        charge_id = obj.get("id")
        stripe_charge_id = str(charge_id) if charge_id else None
        payment_intent = obj.get("payment_intent")
        stripe_payment_intent_id = str(payment_intent) if payment_intent else None
        refunds = obj.get("refunds") if isinstance(obj.get("refunds"), dict) else {}
        refund_data = refunds.get("data") if isinstance(refunds.get("data"), list) else []
        if refund_data and isinstance(refund_data[0], dict) and refund_data[0].get("id"):
            stripe_refund_id = str(refund_data[0]["id"])
        amount = -_to_decimal_amount(obj.get("amount_refunded") or obj.get("amount"))

    currency = _to_upper_currency(obj.get("currency"))
    customer_id, account_id, unlinked = await _resolve_links(
        db,
        stripe_customer_id=stripe_customer_id,
        metadata=metadata,
    )

    payment_event = StripePaymentEvent(
        stripe_event_id=event_id,
        stripe_event_type=event_type,
        stripe_payment_intent_id=stripe_payment_intent_id,
        stripe_charge_id=stripe_charge_id,
        stripe_refund_id=stripe_refund_id,
        stripe_customer_id=stripe_customer_id,
        customer_id=customer_id,
        account_id=account_id,
        amount=amount,
        currency=currency,
        occurred_at=event_created_at,
        unlinked=unlinked,
        source=source,
        payload_json=event,
        processing_status="processed",
        processed_at=datetime.now(timezone.utc),
    )
    db.add(payment_event)

    await _sync_income_from_payment_event(
        db,
        event_type=event_type,
        event_id=event_id,
        occurred_at=event_created_at,
        stripe_payment_intent_id=stripe_payment_intent_id,
        stripe_refund_id=stripe_refund_id,
        stripe_charge_id=stripe_charge_id,
        customer_id=customer_id,
        account_id=account_id,
        amount=amount,
        currency=currency,
    )
    return "processed"


async def _sync_income_from_payment_event(
    db: AsyncSession,
    *,
    event_type: str,
    event_id: str,
    occurred_at: datetime,
    stripe_payment_intent_id: str | None,
    stripe_refund_id: str | None,
    stripe_charge_id: str | None,
    customer_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    amount: Decimal,
    currency: str,
) -> None:
    if event_type == "payment_intent.succeeded":
        stripe_payment_key = f"pi:{stripe_payment_intent_id or event_id}"
        description = f"Stripe payment {stripe_payment_intent_id or event_id}"
        category = "subscription"
    else:
        refund_key = stripe_refund_id or stripe_charge_id or event_id
        stripe_payment_key = f"refund:{refund_key}"
        description = f"Stripe refund {refund_key}"
        category = "refund"

    existing = await db.execute(
        select(IncomeEntry.id).where(IncomeEntry.stripe_payment_id == stripe_payment_key)
    )
    if existing.scalar_one_or_none() is not None:
        return

    mxn_to_usd = await _get_mxn_to_usd(db)
    metadata = build_income_metadata(
        {
            "stripe_event_id": event_id,
            "stripe_event_type": event_type,
            "origin": "stripe",
        },
        "one_time",
        None,
    )

    income = IncomeEntry(
        source="stripe",
        stripe_payment_id=stripe_payment_key,
        stripe_invoice_id=None,
        customer_id=customer_id,
        account_id=account_id,
        description=description,
        amount=amount,
        currency=currency,
        amount_usd=_to_usd(amount, currency, mxn_to_usd),
        category=category,
        date=occurred_at.date(),
        is_recurring=False,
        metadata_json=metadata,
        created_by=None,
    )
    db.add(income)


async def _process_payout_event(db: AsyncSession, *, event: dict[str, Any], source: str) -> str:
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    event_created_at = _to_datetime(event.get("created"))

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    metadata = _extract_metadata(obj)

    payout_id = str(obj.get("id") or "")
    amount = _to_decimal_amount(obj.get("amount"))
    currency = _to_upper_currency(obj.get("currency"))
    arrival = _to_datetime(obj.get("arrival_date")).date() if obj.get("arrival_date") else None
    account_id = _resolve_account_id_from_metadata(metadata)
    status = str(obj.get("status") or "") or ("paid" if event_type == "payout.paid" else "failed")

    payout_event = StripePayoutEvent(
        stripe_event_id=event_id,
        stripe_event_type=event_type,
        stripe_payout_id=payout_id,
        status=status,
        amount=amount,
        currency=currency,
        arrival_date=arrival,
        paid_at=event_created_at if event_type == "payout.paid" else None,
        failed_at=event_created_at if event_type == "payout.failed" else None,
        account_id=account_id,
        unlinked=account_id is None,
        source=source,
        payload_json=event,
        processing_status="processed",
        processed_at=datetime.now(timezone.utc),
    )
    db.add(payout_event)
    return "processed"


def _list_events_sync(
    *,
    stripe_secret_key: str,
    start_timestamp: int | None,
    end_timestamp: int | None,
    max_events: int,
) -> list[dict[str, Any]]:
    stripe.api_key = stripe_secret_key

    params: dict[str, Any] = {
        "limit": min(100, max_events),
        "types": sorted(SUPPORTED_STRIPE_EVENT_TYPES),
    }
    created: dict[str, int] = {}
    if start_timestamp is not None:
        created["gte"] = start_timestamp
    if end_timestamp is not None:
        created["lte"] = end_timestamp
    if created:
        params["created"] = created

    events = stripe.Event.list(**params)
    collected: list[dict[str, Any]] = []
    for item in events.auto_paging_iter():
        if hasattr(item, "to_dict_recursive"):
            collected.append(item.to_dict_recursive())
        else:
            collected.append(dict(item))
        if len(collected) >= max_events:
            break
    return collected


async def reconcile_stripe_events(
    db: AsyncSession,
    *,
    backfill: bool,
    start_date: date | None,
    end_date: date | None,
    max_events: int,
) -> dict[str, int]:
    stripe_secret_key = settings.eva_stripe_secret_key.strip()
    if not stripe_secret_key:
        raise ValueError("Stripe secret key is not configured")

    start_ts: int | None = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()) if start_date else None
    end_ts: int | None = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp()) if end_date else None

    if not backfill and start_ts is None:
        payment_latest = (await db.execute(select(func.max(StripePaymentEvent.occurred_at)))).scalar_one_or_none()
        payout_latest = (await db.execute(select(func.max(StripePayoutEvent.occurred_at)))).scalar_one_or_none()
        candidates = [d for d in (payment_latest, payout_latest) if d is not None]
        if candidates:
            latest_seen = max(candidates)
            start_ts = max(int(latest_seen.timestamp()) - 3600, 0)

    raw_events = await asyncio.to_thread(
        _list_events_sync,
        stripe_secret_key=stripe_secret_key,
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        max_events=max_events,
    )

    sorted_events = sorted(raw_events, key=lambda item: int(item.get("created") or 0))
    stats = {
        "fetched_events": len(sorted_events),
        "processed_events": 0,
        "duplicate_events": 0,
        "ignored_events": 0,
        "failed_events": 0,
    }

    for event in sorted_events:
        try:
            status = await apply_stripe_event(db, event, source="reconcile")
        except Exception:
            logger.exception("Failed to process stripe event %s", event.get("id"))
            status = "failed"

        if status == "processed":
            stats["processed_events"] += 1
        elif status == "duplicate":
            stats["duplicate_events"] += 1
        elif status == "ignored":
            stats["ignored_events"] += 1
        else:
            stats["failed_events"] += 1

    return stats


async def run_nightly_stripe_reconciliation_once() -> None:
    if not settings.stripe_reconciliation_enabled:
        return
    if not settings.eva_stripe_secret_key.strip():
        return

    async with async_session() as db:
        try:
            stats = await reconcile_stripe_events(
                db,
                backfill=False,
                start_date=None,
                end_date=None,
                max_events=500,
            )
            await db.commit()
            logger.info("Nightly Stripe reconciliation completed: %s", stats)
        except Exception:
            await db.rollback()
            logger.exception("Nightly Stripe reconciliation failed")


async def stripe_reconciliation_runner_loop(stop_event: asyncio.Event) -> None:
    interval = max(int(settings.stripe_reconciliation_interval_seconds), 300)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            await run_nightly_stripe_reconciliation_once()
