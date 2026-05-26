from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # ── Credentials ───────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ── Profile ───────────────────────────────────
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    age: Mapped[int | None] = mapped_column(nullable=True)
    health_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated list of conditions e.g. diabetes, hypertension",
    )

    # ── Status ────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ── Relationships ─────────────────────────────
    # One user → many chats
    chats: Mapped[list["Chat"]] = relationship(  # noqa: F821
        "Chat",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
