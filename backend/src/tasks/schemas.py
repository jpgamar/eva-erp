from __future__ import annotations

import uuid
import datetime as _dt
from pydantic import BaseModel


class BoardCreate(BaseModel):
    name: str
    description: str | None = None


class BoardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ColumnCreate(BaseModel):
    name: str
    color: str = "#6b7280"


class ColumnUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    color: str | None = None


class TaskCreate(BaseModel):
    board_id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    priority: str = "medium"
    due_date: _dt.date | None = None
    labels: list[str] | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    priority: str | None = None
    due_date: _dt.date | None = None
    labels: list[str] | None = None


class TaskMove(BaseModel):
    column_id: uuid.UUID
    position: float


class CommentCreate(BaseModel):
    content: str


# Response models
class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class ActivityResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    old_value: str | None
    new_value: str | None
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: uuid.UUID
    column_id: uuid.UUID
    board_id: uuid.UUID
    title: str
    description: str | None
    assignee_id: uuid.UUID | None
    priority: str
    due_date: _dt.date | None
    labels: list[str] | None
    position: float
    source_meeting_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class TaskDetailResponse(TaskResponse):
    comments: list[CommentResponse] = []


class ColumnResponse(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position: int
    color: str
    tasks: list[TaskResponse] = []
    model_config = {"from_attributes": True}


class BoardResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    position: int
    created_by: uuid.UUID
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


class BoardDetailResponse(BoardResponse):
    columns: list[ColumnResponse] = []
