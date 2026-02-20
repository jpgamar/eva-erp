from __future__ import annotations

import uuid
import datetime as _dt
from decimal import Decimal
from pydantic import BaseModel


class PeriodCreate(BaseModel):
    name: str
    start_date: _dt.date
    end_date: _dt.date
    status: str = "upcoming"


class ObjectiveCreate(BaseModel):
    period_id: uuid.UUID
    title: str
    description: str | None = None
    owner_id: uuid.UUID
    position: int = 0


class ObjectiveUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    position: int | None = None


class KeyResultCreate(BaseModel):
    objective_id: uuid.UUID
    title: str
    target_value: Decimal
    unit: str = "%"
    tracking_mode: str = "manual"
    auto_metric: str | None = None
    start_value: Decimal = Decimal("0")


class KeyResultUpdate(BaseModel):
    title: str | None = None
    current_value: Decimal | None = None
    target_value: Decimal | None = None


class KeyResultResponse(BaseModel):
    id: uuid.UUID
    objective_id: uuid.UUID
    title: str
    target_value: Decimal
    current_value: Decimal
    unit: str
    tracking_mode: str
    auto_metric: str | None
    start_value: Decimal
    progress_pct: Decimal
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class ObjectiveResponse(BaseModel):
    id: uuid.UUID
    period_id: uuid.UUID
    title: str
    description: str | None
    owner_id: uuid.UUID
    position: int
    status: str
    key_results: list[KeyResultResponse] = []
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class PeriodResponse(BaseModel):
    id: uuid.UUID
    name: str
    start_date: _dt.date
    end_date: _dt.date
    status: str
    objectives: list[ObjectiveResponse] = []
    created_at: _dt.datetime
    model_config = {"from_attributes": True}
