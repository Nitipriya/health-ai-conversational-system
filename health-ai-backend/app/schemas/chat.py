import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────
class CreateChatRequest(BaseModel):
    title: str = Field(default="New Chat", min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)


class UpdateChatRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)


# ── Responses ─────────────────────────────────────────────────────────────────
class ChatResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatListResponse(BaseModel):
    chats: list[ChatResponse]
    total: int
