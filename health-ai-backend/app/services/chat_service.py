import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import get_logger
from app.db.models.chat import Chat
from app.db.models.context import ChatContext
from app.schemas.chat import CreateChatRequest, UpdateChatRequest

logger = get_logger(__name__)


async def create_chat(
    data: CreateChatRequest,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Chat:
    """Create a new chat and its empty context row."""
    chat = Chat(
        user_id=user_id,
        title=data.title,
        description=data.description,
    )
    db.add(chat)
    await db.flush()  # get chat.id before creating context

    # Create the context row now so it always exists when messages arrive
    context = ChatContext(chat_id=chat.id)
    db.add(context)

    logger.info(f"Chat created: id={chat.id} user_id={user_id}")
    return chat


async def get_user_chats(
    user_id: uuid.UUID,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Chat], int]:
    """
    Return a paginated list of the user's active (non-deleted) chats.
    Returns (chats, total_count).
    """
    base_query = (
        select(Chat)
        .where(Chat.user_id == user_id, Chat.is_deleted == False)  # noqa: E712
        .order_by(Chat.updated_at.desc())
    )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated results
    offset = (page - 1) * page_size
    result = await db.execute(base_query.offset(offset).limit(page_size))
    chats = list(result.scalars().all())

    return chats, total


async def get_chat(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Chat:
    """
    Get a single chat by ID.
    Raises NotFoundException if not found.
    Raises ForbiddenException if the chat belongs to a different user.
    """
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.is_deleted == False)  # noqa: E712
    )
    chat = result.scalar_one_or_none()

    if not chat:
        raise NotFoundException("Chat")

    if chat.user_id != user_id:
        raise ForbiddenException("This chat belongs to another user")

    return chat


async def update_chat(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    data: UpdateChatRequest,
    db: AsyncSession,
) -> Chat:
    """Update a chat's title or description."""
    chat = await get_chat(chat_id, user_id, db)

    if data.title is not None:
        chat.title = data.title
    if data.description is not None:
        chat.description = data.description

    await db.flush()
    logger.info(f"Chat updated: id={chat_id}")
    return chat


async def delete_chat(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Soft delete a chat — marks is_deleted=True, never removes from DB.
    Medical history must always be recoverable.
    """
    chat = await get_chat(chat_id, user_id, db)
    chat.is_deleted = True
    await db.flush()
    logger.info(f"Chat soft-deleted: id={chat_id}")
