import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Chat(Base):
    __tablename__ = "chats"

    # ── Foreign key ───────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Fields ────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Chat",
        comment="Auto-generated or user-renamed chat title",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Soft delete ───────────────────────────────
    # We never hard-delete chats — we just mark them deleted
    # so medical history is always recoverable
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    # ── Relationships ─────────────────────────────
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="chats",
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="select",
    )
    context: Mapped["ChatContext | None"] = relationship(  # noqa: F821
        "ChatContext",
        back_populates="chat",
        uselist=False,   # one-to-one
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Chat id={self.id} title={self.title!r} user_id={self.user_id}>"
