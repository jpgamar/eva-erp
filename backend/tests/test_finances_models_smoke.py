from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.finances.models import IncomeEntry


def test_income_entry_model_import_and_instantiation_smoke() -> None:
    entry = IncomeEntry(
        source="manual",
        description="Smoke test",
        amount=Decimal("10.00"),
        currency="MXN",
        amount_usd=Decimal("10.00"),
        category="subscription",
        date=datetime.now(timezone.utc).date(),
    )

    assert entry.__tablename__ == "income_entries"
    assert entry.source == "manual"
