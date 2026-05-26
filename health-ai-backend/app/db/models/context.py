import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatContext(Base):
    __tablename__ = "chat_contexts"

    # ── Foreign key (one-to-one with Chat) ────────
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,     # enforces one-to-one at DB level
        index=True,
    )

    # ── Rolling summary ───────────────────────────
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "AI-generated rolling summary of the conversation so far. "
            "Injected into each new prompt instead of full message history."
        ),
    )

    # ── Tracking ──────────────────────────────────
    last_summarized_at_message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="How many messages existed when summary was last updated",
    )
    total_tokens_saved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Estimated tokens saved by using summary instead of full history",
    )

    # ── Relationship ──────────────────────────────
    chat: Mapped["Chat"] = relationship(  # noqa: F821
        "Chat",
        back_populates="context",
    )

    def __repr__(self) -> str:
        preview = self.summary[:60] + "..." if self.summary and len(self.summary) > 60 else self.summary
        return f"<ChatContext chat_id={self.chat_id} summary={preview!r}>"
