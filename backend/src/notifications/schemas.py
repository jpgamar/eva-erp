import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    link: str | None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int


class UnreadCountResponse(BaseModel):
    count: int
