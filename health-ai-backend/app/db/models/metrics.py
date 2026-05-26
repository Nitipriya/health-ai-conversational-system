import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelMetrics(Base):
    """
    One row per AI response. Lets you monitor:
    - which provider is faster / more reliable
    - token usage over time (useful if you later switch to paid tier)
    - fallback rate (how often Groq fails and Gemini takes over)
    """

    __tablename__ = "model_metrics"

    # ── Foreign keys ──────────────────────────────
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Provider info ─────────────────────────────
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="groq | gemini",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    was_fallback: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="True if primary provider failed and this used the fallback",
    )

    # ── Performance ───────────────────────────────
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Outcome ───────────────────────────────────
    success: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. rate_limit | timeout | api_error — only set if success=False",
    )

    def __repr__(self) -> str:
        return (
            f"<ModelMetrics provider={self.provider} model={self.model_name} "
            f"tokens={self.total_tokens} time={self.response_time_ms}ms>"
        )
