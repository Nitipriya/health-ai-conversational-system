import time

from groq import AsyncGroq, APIConnectionError, APIStatusError, RateLimitError

from app.ai.model_client import AIResponse, BaseModelClient
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GroqClient(BaseModelClient):
    """
    Wraps the Groq SDK.
    Primary provider — used for RAT reasoning and main chat responses.
    Model: llama-3.3-70b-versatile (free tier, very capable)
    """

    def __init__(self):
        self._client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout_seconds,
        )
        self.model = settings.groq_model

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AIResponse:
        """
        Call Groq's chat completions endpoint.
        Raises RuntimeError on failure so the caller can trigger fallback.
        """
        start = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RateLimitError as e:
            logger.warning(f"Groq rate limit hit: {e}")
            raise RuntimeError("groq_rate_limit") from e
        except APIConnectionError as e:
            logger.error(f"Groq connection error: {e}")
            raise RuntimeError("groq_connection_error") from e
        except APIStatusError as e:
            logger.error(f"Groq API error {e.status_code}: {e.message}")
            raise RuntimeError(f"groq_api_error_{e.status_code}") from e

        elapsed_ms = round((time.perf_counter() - start) * 1000)

        usage = response.usage
        content = response.choices[0].message.content or ""

        logger.debug(
            f"Groq response: {usage.total_tokens} tokens, {elapsed_ms}ms"
        )

        return AIResponse(
            content=content,
            model=self.model,
            provider="groq",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            response_time_ms=elapsed_ms,
        )

    async def is_available(self) -> bool:
        """Ping Groq with a minimal request to check availability."""
        try:
            await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
