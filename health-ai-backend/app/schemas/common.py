import uuid
from datetime import datetime

from pydantic import BaseModel


class BaseResponse(BaseModel):
    """Every response includes id + timestamps."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Generic success message response."""
    message: str


class PaginatedResponse(BaseModel):
    """Wrap any list response with pagination info."""
    total: int
    page: int
    page_size: int
    has_more: bool
