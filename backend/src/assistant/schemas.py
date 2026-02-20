import uuid
from datetime import datetime
from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    messages_json: list
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
