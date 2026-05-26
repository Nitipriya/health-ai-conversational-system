import uuid
from typing import Literal

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Role must be exactly one of these — enforced at DB level
RoleEnum = Enum("user", "assistant", name="message_role_enum")


class Message(Base):
    __tablename__ = "messages"

    # ── Foreign key ───────────────────────────────
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Content ───────────────────────────────────
    role: Mapped[Literal["user", "assistant"]] = mapped_column(
        RoleEnum,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The actual message text",
    )

    # ── AI metadata (only filled for assistant messages) ──
    model_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. llama-3.3-70b-versatile or gemini-1.5-flash",
    )
    provider_used: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="groq or gemini",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Model's self-reported confidence 0.0–1.0",
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="How long the AI took to respond in milliseconds",
    )

    # ── Safety ────────────────────────────────────
    safety_flagged: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    safety_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. self_harm, medication_dosage, emergency",
    )

    # ── Relationships ─────────────────────────────
    chat: Mapped["Chat"] = relationship(  # noqa: F821
        "Chat",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        return f"<Message id={self.id} role={self.role} chat_id={self.chat_id} content={preview!r}>"
