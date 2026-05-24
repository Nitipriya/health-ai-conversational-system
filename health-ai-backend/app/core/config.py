from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    app_name: str = "Health AI"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ──────────────────────────────────
    database_url: str

    # ── JWT ───────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── Groq ──────────────────────────────────────
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: int = 60

    # ── Gemini ────────────────────────────────────
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    gemini_timeout_seconds: int = 30

    # ── AI behaviour ──────────────────────────────
    primary_ai_provider: Literal["groq", "gemini"] = "groq"
    fallback_ai_provider: Literal["groq", "gemini"] = "gemini"

    # ── Context ───────────────────────────────────
    context_update_every_n_messages: int = 5
    context_max_tokens: int = 1500

    # ── Rate limiting ─────────────────────────────
    rate_limit_per_minute: int = 30

    # ── Safety ────────────────────────────────────
    safety_classifier_provider: Literal["groq", "gemini"] = "gemini"

    # ── Derived helpers ───────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def access_token_expire_seconds(self) -> int:
        return self.access_token_expire_minutes * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.refresh_token_expire_days * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    """
    Cached singleton — import and call this everywhere.
    The cache means .env is read exactly once at startup.

    Usage:
        from app.core.config import get_settings
        settings = get_settings()
    """
    return Settings()
