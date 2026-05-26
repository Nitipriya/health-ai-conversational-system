import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────
class SendMessageRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message to the health AI",
    )


# ── Responses ─────────────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    model_used: str | None
    provider_used: str | None
    confidence_score: float | None
    tokens_used: int | None
    response_time_ms: int | None
    safety_flagged: bool
    safety_category: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageResponse(BaseModel):
    """
    Returned after a user sends a message.
    Contains both the saved user message and the AI's response.
    """
    user_message: MessageResponse
    ai_response: MessageResponse


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
