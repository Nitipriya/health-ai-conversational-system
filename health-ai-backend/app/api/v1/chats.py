import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limiter import default_limit, limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.chat import (
    ChatListResponse,
    ChatResponse,
    CreateChatRequest,
    UpdateChatRequest,
)
from app.schemas.common import MessageResponse
from app.services.chat_service import (
    create_chat,
    delete_chat,
    get_chat,
    get_user_chats,
    update_chat,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatResponse, status_code=201)
@limiter.limit(default_limit)
async def create_new_chat(
    request: Request,
    data: CreateChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new chat session.
    A blank context row is created automatically alongside it.
    """
    chat = await create_chat(data, current_user.id, db)
    return chat


@router.get("", response_model=ChatListResponse)
@limiter.limit(default_limit)
async def list_chats(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all active chats for the logged-in user.
    Sorted by most recently updated. Supports pagination via ?page=1&page_size=20
    """
    chats, total = await get_user_chats(current_user.id, db, page, page_size)
    return ChatListResponse(chats=chats, total=total)


@router.get("/{chat_id}", response_model=ChatResponse)
@limiter.limit(default_limit)
async def get_single_chat(
    request: Request,
    chat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single chat by its ID."""
    chat = await get_chat(chat_id, current_user.id, db)
    return chat


@router.patch("/{chat_id}", response_model=ChatResponse)
@limiter.limit(default_limit)
async def update_existing_chat(
    request: Request,
    chat_id: uuid.UUID,
    data: UpdateChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a chat's title or description."""
    chat = await update_chat(chat_id, current_user.id, data, db)
    return chat


@router.delete("/{chat_id}", response_model=MessageResponse)
@limiter.limit(default_limit)
async def delete_existing_chat(
    request: Request,
    chat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete a chat. It won't appear in your list anymore
    but the data is kept in the database for medical audit purposes.
    """
    await delete_chat(chat_id, current_user.id, db)
    return MessageResponse(message="Chat deleted successfully")
