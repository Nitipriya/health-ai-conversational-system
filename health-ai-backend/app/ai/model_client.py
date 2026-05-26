from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    """
    Standardised response object returned by both Groq and Gemini.
    Routes and services only ever deal with this — never raw SDK objects.
    """
    content: str           # the text response
    model: str             # which model was used e.g. "llama-3.3-70b-versatile"
    provider: str          # "groq" or "gemini"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int


class BaseModelClient(ABC):
    """
    Every AI provider client must implement these two methods.
    This means you can swap Groq for any other provider in one place.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> AIResponse:
        """
        Send a list of messages and get a response.

        `messages` format:
          [
            {"role": "system", "content": "..."},
            {"role": "user",   "content": "..."},
          ]
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Quick health check — returns True if the provider is reachable."""
        ...
