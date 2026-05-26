import json
import re

from app.ai.gemini_client import GeminiClient
from app.ai.groq_client import GroqClient
from app.ai.model_client import AIResponse
from app.ai.prompts import build_chat_prompt, build_rat_prompt
from app.core.logging import get_logger

logger = get_logger(__name__)

# Singleton clients — created once, reused for all requests
_groq = GroqClient()
_gemini = GeminiClient()


async def get_ai_response(
    user_message: str,
    context_summary: str | None,
    user_health_conditions: str | None,
) -> tuple[AIResponse, float, str]:
    """
    Main entry point for getting an AI response.

    Strategy:
    1. Try Groq with RAT prompting (best quality)
    2. If Groq fails → fall back to Gemini with RAT prompting
    3. If both fail → raise RuntimeError

    Returns:
        (AIResponse, confidence_score, final_answer_text)
    """
    # Build the RAT prompt — asks the model to reason before answering
    rat_messages = build_rat_prompt(user_message)

    # Inject context and health profile into the messages
    if context_summary or user_health_conditions:
        chat_messages = build_chat_prompt(
            user_message, context_summary, user_health_conditions
        )
        # Merge: use RAT system prompt but include context
        rat_messages = [rat_messages[0]] + chat_messages[1:] + [rat_messages[-1]]

    # ── Try Groq first ────────────────────────────────────────────────────────
    raw_response = None
    was_fallback = False

    try:
        logger.info("Calling Groq (primary)")
        raw_response = await _groq.chat(
            messages=rat_messages,
            temperature=0.3,
            max_tokens=1200,
        )
    except RuntimeError as e:
        logger.warning(f"Groq failed ({e}), falling back to Gemini")

    # ── Fall back to Gemini ───────────────────────────────────────────────────
    if raw_response is None:
        try:
            logger.info("Calling Gemini (fallback)")
            raw_response = await _gemini.chat(
                messages=rat_messages,
                temperature=0.3,
                max_tokens=1200,
            )
            was_fallback = True
        except RuntimeError as e:
            logger.error(f"Both providers failed. Last error: {e}")
            raise RuntimeError("All AI providers are unavailable") from e

    # ── Parse RAT JSON response ───────────────────────────────────────────────
    answer, confidence = _parse_rat_response(raw_response.content)

    # Mark in the response object whether this was a fallback
    raw_response.provider = (
        f"{raw_response.provider}_fallback" if was_fallback else raw_response.provider
    )

    return raw_response, confidence, answer


def _parse_rat_response(raw_content: str) -> tuple[str, float]:
    """
    Parse the JSON response from RAT prompting.

    Returns (answer_text, confidence_score).
    Falls back gracefully if the model didn't return valid JSON.
    """
    # Strip markdown code fences if the model wrapped the JSON
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_content).strip()

    try:
        data = json.loads(cleaned)
        answer = data.get("answer", "").strip()
        disclaimer = data.get("disclaimer", "").strip()
        confidence = float(data.get("confidence", 0.7))

        # Append disclaimer to answer if present
        if disclaimer and disclaimer not in answer:
            answer = f"{answer}\n\n_{disclaimer}_"

        if answer:
            return answer, confidence

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"RAT JSON parse failed: {e} — using raw content as answer")

    # Fallback: return the raw content as-is with default confidence
    return raw_content.strip(), 0.6
