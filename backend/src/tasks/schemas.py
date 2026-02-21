from __future__ import annotations

import uuid
import datetime as _dt
from pydantic import BaseModel


# Board schemas
class BoardCreate(BaseModel):
    name: str
    description: str | None = None


class BoardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class BoardResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_by: uuid.UUID
    created_at: _dt.datetime
    model_config = {"from_attributes": True}


# Task schemas
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    priority: str = "medium"
    due_date: _dt.date | None = None
    labels: list[str] | None = None
    status: str = "todo"
    board_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    priority: str | None = None
    due_date: _dt.date | None = None
    labels: list[str] | None = None
    status: str | None = None
    board_id: uuid.UUID | None = None


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


class TaskResponse(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    assignee_id: uuid.UUID | None
    priority: str
    due_date: _dt.date | None
    labels: list[str] | None
    source_meeting_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: _dt.datetime
    updated_at: _dt.datetime
    model_config = {"from_attributes": True}


class TaskDetailResponse(TaskResponse):
    comments: list[CommentResponse] = []
