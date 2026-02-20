from __future__ import annotations

import uuid
import datetime as _dt
from pydantic import BaseModel


class ActionItem(BaseModel):
    description: str
    assignee_id: uuid.UUID | None = None
    due_date: str | None = None
    completed: bool = False
    linked_task_id: uuid.UUID | None = None


class MeetingCreate(BaseModel):
    title: str
    date: _dt.datetime
    duration_minutes: int | None = None
    type: str = "internal"
    attendees: list[str] | None = None
    notes_markdown: str | None = None
    action_items: list[ActionItem] | None = None
    prospect_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    date: _dt.datetime | None = None
    duration_minutes: int | None = None
    type: str | None = None
    attendees: list[str] | None = None
    notes_markdown: str | None = None
    action_items: list[ActionItem] | None = None


class MeetingResponse(BaseModel):
    id: uuid.UUID
    title: str
    date: _dt.datetime
    duration_minutes: int | None
    type: str
    attendees: list[str] | None
    notes_markdown: str | None
    action_items_json: list | None
    prospect_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}
