import uuid

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rat_reasoner import get_ai_response
from app.core.exceptions import AIProviderException
from app.core.logging import get_logger
from app.db.models.message import Message
from app.db.models.metrics import ModelMetrics
from app.db.models.safety import SafetyEvent
from app.db.models.user import User
from app.schemas.message import MessageResponse, SendMessageResponse
from app.services.context_service import get_context_summary
from app.tasks.context_updater import run_context_update
from app.services.safety_service import (
    SafetyResult,
    build_safety_response_message,
    classify_message,
)

logger = get_logger(__name__)


async def send_message(
    chat_id: uuid.UUID,
    user: User,
    content: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> SendMessageResponse:
    """
    The core message loop. Every message goes through this exactly:

    1. Save the user's message to DB
    2. Run safety classification (Gemini, keyword + LLM)
    3. If unsafe → return a safety response, log the event, done
    4. Fetch rolling context summary
    5. Call AI (Groq → Gemini fallback) with RAT prompting
    6. Save the AI response to DB
    7. Save model metrics
    8. Schedule context update as background task
    9. Return both messages to the client
    """

    # ── Step 1: Save user message ─────────────────────────────────────────────
    user_message = Message(
        chat_id=chat_id,
        role="user",
        content=content,
    )
    db.add(user_message)
    await db.flush()
    logger.info(f"User message saved: id={user_message.id}")

    # ── Step 2: Safety classification ─────────────────────────────────────────
    safety_result: SafetyResult = await classify_message(content)

    # ── Step 3: Handle unsafe messages ────────────────────────────────────────
    if not safety_result.is_safe:
        logger.warning(
            f"Message flagged: category={safety_result.category} "
            f"severity={safety_result.severity} user_id={user.id}"
        )

        # Update the user message row with safety flag
        user_message.safety_flagged = True
        user_message.safety_category = safety_result.category

        # Log the safety event for audit
        safety_event = SafetyEvent(
            message_id=user_message.id,
            chat_id=chat_id,
            user_id=user.id,
            category=safety_result.category,
            severity=safety_result.severity,
            classifier_reasoning=safety_result.reasoning,
            action_taken=safety_result.action,
        )
        db.add(safety_event)

        # Build the safety response
        safety_content = build_safety_response_message(safety_result)
        ai_message = Message(
            chat_id=chat_id,
            role="assistant",
            content=safety_content,
            safety_flagged=True,
            safety_category=safety_result.category,
            model_used="safety-classifier",
            provider_used="gemini",
        )
        db.add(ai_message)
        await db.flush()

        return SendMessageResponse(
            user_message=MessageResponse.model_validate(user_message),
            ai_response=MessageResponse.model_validate(ai_message),
        )

    # ── Step 4: Fetch context summary ─────────────────────────────────────────
    context_summary = await get_context_summary(chat_id, db)

    # ── Step 5: Get AI response ───────────────────────────────────────────────
    try:
        ai_response, confidence, answer = await get_ai_response(
            user_message=content,
            context_summary=context_summary,
            user_health_conditions=user.health_conditions,
        )
    except RuntimeError as e:
        logger.error(f"AI provider error: {e}")
        raise AIProviderException(
            "Our AI is temporarily unavailable. Please try again in a moment."
        ) from e

    # ── Step 6: Save AI response ──────────────────────────────────────────────
    provider = ai_response.provider.replace("_fallback", "")
    ai_message = Message(
        chat_id=chat_id,
        role="assistant",
        content=answer,
        model_used=ai_response.model,
        provider_used=provider,
        confidence_score=confidence,
        tokens_used=ai_response.total_tokens,
        response_time_ms=ai_response.response_time_ms,
        safety_flagged=False,
    )
    db.add(ai_message)
    await db.flush()

    # ── Step 7: Save model metrics ────────────────────────────────────────────
    metrics = ModelMetrics(
        message_id=ai_message.id,
        user_id=user.id,
        provider=provider,
        model_name=ai_response.model,
        was_fallback="_fallback" in ai_response.provider,
        prompt_tokens=ai_response.prompt_tokens,
        completion_tokens=ai_response.completion_tokens,
        total_tokens=ai_response.total_tokens,
        response_time_ms=ai_response.response_time_ms,
        confidence_score=confidence,
        success=True,
    )
    db.add(metrics)
    await db.flush()

    logger.info(
        f"AI response saved: provider={provider} "
        f"tokens={ai_response.total_tokens} time={ai_response.response_time_ms}ms"
    )

    # ── Step 8: Schedule context update in background ─────────────────────────
    # This runs AFTER the response is sent to the user — they never wait for it
    background_tasks.add_task(run_context_update, chat_id)

    # ── Step 9: Return both messages ──────────────────────────────────────────
    return SendMessageResponse(
        user_message=MessageResponse.model_validate(user_message),
        ai_response=MessageResponse.model_validate(ai_message),
    )


async def get_chat_messages(
    chat_id: uuid.UUID,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int]:
    """Return paginated message history for a chat, oldest first."""
    base_query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    )

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(base_query.offset(offset).limit(page_size))
    messages = list(result.scalars().all())

    return messages, total
