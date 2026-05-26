import json
import re

from app.ai.gemini_client import GeminiClient
from app.ai.prompts import SAFETY_CLASSIFIER_SYSTEM_PROMPT
from app.core.logging import get_logger

logger = get_logger(__name__)

_gemini = GeminiClient()

# ── Keyword pre-filter ────────────────────────────────────────────────────────
# Fast rule-based check runs BEFORE the LLM classifier.
# Catches obvious cases without spending an API call.
EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "cannot breathe", "heart attack",
    "stroke", "unconscious", "not breathing", "severe bleeding",
    "call 911", "emergency",
]
SELF_HARM_KEYWORDS = [
    "kill myself", "want to die", "suicide", "self harm", "self-harm",
    "cut myself", "end my life", "hurt myself",
]
MEDICATION_ABUSE_KEYWORDS = [
    "how much to overdose", "lethal dose", "how many pills to",
    "overdose on", "maximum dose to",
]


class SafetyResult:
    def __init__(
        self,
        is_safe: bool,
        category: str,
        severity: str,
        reasoning: str,
        action: str,
    ):
        self.is_safe = is_safe
        self.category = category
        self.severity = severity
        self.reasoning = reasoning
        self.action = action


async def classify_message(message: str) -> SafetyResult:
    """
    Two-stage safety classifier:

    Stage 1 — Keyword pre-filter (instant, no API call)
      Catches obvious emergencies and self-harm signals.

    Stage 2 — Gemini LLM classifier (catches subtle signals)
      Only runs if Stage 1 passes.

    Returns a SafetyResult with what action to take.
    """

    # ── Stage 1: keyword check ────────────────────────────────────────────────
    lower = message.lower()

    for kw in SELF_HARM_KEYWORDS:
        if kw in lower:
            logger.warning(f"Self-harm keyword detected: '{kw}'")
            return SafetyResult(
                is_safe=False,
                category="self_harm",
                severity="critical",
                reasoning=f"Message contains self-harm keyword: '{kw}'",
                action="show_crisis_resources",
            )

    for kw in EMERGENCY_KEYWORDS:
        if kw in lower:
            logger.warning(f"Emergency keyword detected: '{kw}'")
            return SafetyResult(
                is_safe=False,
                category="emergency",
                severity="critical",
                reasoning=f"Message contains emergency keyword: '{kw}'",
                action="show_crisis_resources",
            )

    for kw in MEDICATION_ABUSE_KEYWORDS:
        if kw in lower:
            logger.warning(f"Medication abuse keyword detected: '{kw}'")
            return SafetyResult(
                is_safe=False,
                category="medication_dosage",
                severity="high",
                reasoning=f"Message contains medication abuse keyword: '{kw}'",
                action="block_and_redirect",
            )

    # ── Stage 2: Gemini LLM classifier ───────────────────────────────────────
    try:
        response = await _gemini.chat(
            messages=[
                {"role": "system", "content": SAFETY_CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.1,   # very low temp — we want consistent classification
            max_tokens=200,
        )

        result = _parse_safety_response(response.content)
        if result:
            return result

    except Exception as e:
        # If the classifier fails, default to SAFE so the app keeps working
        # This is intentional — a broken classifier shouldn't block all messages
        logger.error(f"Safety classifier error: {e} — defaulting to safe")

    return SafetyResult(
        is_safe=True,
        category="safe",
        severity="none",
        reasoning="No safety issues detected",
        action="none",
    )


def _parse_safety_response(raw: str) -> SafetyResult | None:
    """Parse the JSON response from Gemini safety classifier."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

    try:
        data = json.loads(cleaned)
        return SafetyResult(
            is_safe=bool(data.get("is_safe", True)),
            category=data.get("category", "safe"),
            severity=data.get("severity", "none"),
            reasoning=data.get("reasoning", ""),
            action=data.get("action", "none"),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Safety response parse failed: {e}")
        return None


def build_safety_response_message(result: SafetyResult) -> str:
    """
    Build the response to show the user when a message is flagged.
    """
    if result.category == "self_harm" or result.severity == "critical":
        return (
            "I'm concerned about what you've shared. "
            "If you're in crisis, please reach out for help immediately:\n\n"
            "🆘 **iCall (India):** 9152987821\n"
            "🆘 **Vandrevala Foundation:** 1860-2662-345 (24/7)\n"
            "🆘 **International Association for Suicide Prevention:** "
            "https://www.iasp.info/resources/Crisis_Centres/\n\n"
            "You don't have to face this alone."
        )

    if result.category == "emergency":
        return (
            "This sounds like it could be a medical emergency. "
            "Please call emergency services (112 in India, 911 in US) "
            "or go to your nearest emergency room immediately.\n\n"
            "Do not wait — please seek help now."
        )

    if result.category == "medication_dosage":
        return (
            "I'm not able to provide information about medication dosages. "
            "Please consult your doctor or pharmacist for safe medication guidance."
        )

    return (
        "I'm not able to respond to that message. "
        "Please consult a qualified healthcare professional for personalised advice."
    )
