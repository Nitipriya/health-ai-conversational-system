import time

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError, ResourceExhausted

from app.ai.model_client import AIResponse, BaseModelClient
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GeminiClient(BaseModelClient):
    """
    Wraps the Google Generative AI SDK.

    Two roles:
    1. Fallback when Groq fails or is rate-limited
    2. Primary provider for safety classification (Gemini Flash is
       better at following strict JSON output schemas than open models)
    """

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_model
        self._model = genai.GenerativeModel(self.model_name)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AIResponse:
        """
        Call Gemini's generate_content endpoint.

        Note: Gemini uses a different message format than OpenAI/Groq.
        We convert here so the rest of the app never has to care.
        """
        start = time.perf_counter()

        # Convert OpenAI-style messages to Gemini format
        gemini_messages, system_instruction = self._convert_messages(messages)

        # Apply system instruction if present
        model = (
            genai.GenerativeModel(
                self.model_name,
                system_instruction=system_instruction,
            )
            if system_instruction
            else self._model
        )

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = await model.generate_content_async(
                gemini_messages,
                generation_config=generation_config,
            )
        except ResourceExhausted as e:
            logger.warning(f"Gemini quota exceeded: {e}")
            raise RuntimeError("gemini_quota_exceeded") from e
        except GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError("gemini_api_error") from e

        elapsed_ms = round((time.perf_counter() - start) * 1000)
        content = response.text or ""

        # Gemini's usage metadata
        usage = response.usage_metadata
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0

        logger.debug(
            f"Gemini response: {prompt_tokens + completion_tokens} tokens, {elapsed_ms}ms"
        )

        return AIResponse(
            content=content,
            model=self.model_name,
            provider="gemini",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            response_time_ms=elapsed_ms,
        )

    def _convert_messages(
        self, messages: list[dict]
    ) -> tuple[list, str | None]:
        """
        Convert OpenAI-style messages to Gemini format.

        OpenAI format: [{"role": "system"/"user"/"assistant", "content": "..."}]
        Gemini format: [{"role": "user"/"model", "parts": ["..."]}]

        System messages are extracted and returned separately as system_instruction.
        """
        system_parts = []
        gemini_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_parts.append(content)
            elif role == "user":
                gemini_messages.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_messages.append({"role": "model", "parts": [content]})

        system_instruction = "\n\n".join(system_parts) if system_parts else None

        # Gemini requires the conversation to start with a user message
        if not gemini_messages:
            gemini_messages = [{"role": "user", "parts": ["Hello"]}]

        return gemini_messages, system_instruction

    async def is_available(self) -> bool:
        """Check Gemini is reachable."""
        try:
            response = await self._model.generate_content_async("hi")
            return bool(response.text)
        except Exception:
            return False
