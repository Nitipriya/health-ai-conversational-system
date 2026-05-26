import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini_client import GeminiClient
from app.ai.prompts import build_summarizer_prompt
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.context import ChatContext
from app.db.models.message import Message

logger = get_logger(__name__)
settings = get_settings()

_gemini = GeminiClient()


async def get_context_summary(
    chat_id: uuid.UUID,
    db: AsyncSession,
) -> str | None:
    """
    Fetch the current rolling summary for a chat.
    Returns None if no summary exists yet (e.g. first few messages).
    """
    result = await db.execute(
        select(ChatContext).where(ChatContext.chat_id == chat_id)
    )
    context = result.scalar_one_or_none()
    return context.summary if context else None


async def maybe_update_context(
    chat_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Check if it's time to update the rolling summary.
    Runs as a background task — user never waits for this.

    Update triggers when:
    - Message count has grown by N since last summarization
      (N = CONTEXT_UPDATE_EVERY_N_MESSAGES from settings, default 5)
    """
    # Get current message count
    count_result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.chat_id == chat_id)
    )
    total_messages = count_result.scalar_one()

    # Get the context row
    ctx_result = await db.execute(
        select(ChatContext).where(ChatContext.chat_id == chat_id)
    )
    context = ctx_result.scalar_one_or_none()

    if not context:
        logger.warning(f"No context row found for chat {chat_id}")
        return

    messages_since_last = total_messages - context.last_summarized_at_message_count

    # Only summarize if enough new messages have come in
    if messages_since_last < settings.context_update_every_n_messages:
        return

    logger.info(
        f"Updating context for chat {chat_id} "
        f"({total_messages} messages, last summarized at {context.last_summarized_at_message_count})"
    )

    await _regenerate_summary(chat_id, context, total_messages, db)


async def _regenerate_summary(
    chat_id: uuid.UUID,
    context: ChatContext,
    total_messages: int,
    db: AsyncSession,
) -> None:
    """
    Fetch recent messages and generate a new rolling summary via Gemini.
    Uses the last 20 messages (enough context, not too many tokens).
    """
    # Fetch recent messages
    msgs_result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent_messages = list(reversed(msgs_result.scalars().all()))

    if not recent_messages:
        return

    # Build prompt for summarizer
    message_dicts = [
        {"role": m.role, "content": m.content}
        for m in recent_messages
    ]
    prompt = build_summarizer_prompt(message_dicts)

    try:
        response = await _gemini.chat(
            messages=prompt,
            temperature=0.2,
            max_tokens=500,
        )
        new_summary = response.content.strip()

        # Estimate tokens saved: full history vs summary length
        full_history_tokens = sum(len(m.content.split()) for m in recent_messages)
        summary_tokens = len(new_summary.split())
        tokens_saved = max(0, full_history_tokens - summary_tokens)

        # Update the context row
        context.summary = new_summary
        context.last_summarized_at_message_count = total_messages
        context.total_tokens_saved += tokens_saved

        await db.commit()
        logger.info(f"Context updated for chat {chat_id} (~{tokens_saved} tokens saved)")

    except Exception as e:
        logger.error(f"Context summarization failed for chat {chat_id}: {e}")
        # Don't re-raise — this is a background task, failure is non-critical
