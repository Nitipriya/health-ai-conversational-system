import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SafetyEvent(Base):
    """
    Every time a message is flagged by the safety classifier,
    we write a row here. Never deleted — full audit trail.
    """

    __tablename__ = "safety_events"

    # ── Foreign keys ──────────────────────────────
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ────────────────────────────
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. self_harm | medication_dosage | emergency | mental_health",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="low | medium | high | critical",
    )
    classifier_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why the classifier flagged this message",
    )

    # ── Response taken ────────────────────────────
    action_taken: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. disclaimer_added | response_blocked | emergency_resources_shown",
    )

    def __repr__(self) -> str:
        return (
            f"<SafetyEvent id={self.id} category={self.category} "
            f"severity={self.severity} user_id={self.user_id}>"
        )
