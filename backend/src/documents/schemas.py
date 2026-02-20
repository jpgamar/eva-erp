import uuid
from datetime import datetime
from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class FolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    position: int
    created_at: datetime
    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    name: str
    folder_id: uuid.UUID
    file_url: str
    file_size: int
    mime_type: str
    description: str | None
    tags: list[str] | None
    uploaded_by: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}
