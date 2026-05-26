import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limiter import default_limit, limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.message import (
    MessageListResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.chat_service import get_chat
from app.services.message_service import get_chat_messages, send_message

router = APIRouter(prefix="/chats/{chat_id}/messages", tags=["messages"])


@router.post("", response_model=SendMessageResponse, status_code=201)
@limiter.limit(default_limit)
async def send_new_message(
    request: Request,
    chat_id: uuid.UUID,
    data: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the health AI.

    Flow:
    1. Validates the message isn't empty
    2. Confirms the chat belongs to this user
    3. Runs safety classification (Gemini)
    4. Builds context from rolling summary
    5. Calls Groq (with Gemini fallback) for the AI response
    6. Saves both messages to DB
    7. Schedules context summarization in the background

    Returns both the saved user message and the AI response.
    """
    # Verify this chat belongs to the current user before doing anything
    await get_chat(chat_id, current_user.id, db)

    result = await send_message(
        chat_id=chat_id,
        user=current_user,
        content=data.content,
        db=db,
        background_tasks=background_tasks,
    )
    return result


@router.get("", response_model=MessageListResponse)
@limiter.limit(default_limit)
async def list_messages(
    request: Request,
    chat_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the full message history for a chat.
    Ordered oldest → newest. Supports pagination via ?page=1&page_size=50
    """
    # Verify ownership
    await get_chat(chat_id, current_user.id, db)

    messages, total = await get_chat_messages(chat_id, db, page, page_size)
    return MessageListResponse(messages=messages, total=total)
