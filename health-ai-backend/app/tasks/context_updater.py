import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.context_service import maybe_update_context

logger = get_logger(__name__)


async def run_context_update(chat_id: uuid.UUID) -> None:
    """
    Standalone background task that opens its OWN database session.

    Why a separate session?
    The request's DB session closes when the response is sent.
    Background tasks run after that — so they need their own session.

    This is called from message_service.py via FastAPI's BackgroundTasks:
        background_tasks.add_task(run_context_update, chat_id)
    """
    async with AsyncSessionLocal() as db:
        try:
            await maybe_update_context(chat_id, db)
        except Exception as e:
            logger.error(
                f"Background context update failed for chat {chat_id}: {e}",
                exc_info=True,
            )
