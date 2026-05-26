import uuid
from datetime import datetime

from pydantic import BaseModel


class ContextResponse(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    summary: str | None
    last_summarized_at_message_count: int
    total_tokens_saved: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
