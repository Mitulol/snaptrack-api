from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FlagReason(str, enum.Enum):
    SPAM = "spam"
    NUDITY = "nudity"
    VIOLENCE = "violence"
    COPYRIGHT = "copyright"
    OTHER = "other"


class FlagStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"


class FlagResolution(str, enum.Enum):
    DISMISSED = "dismissed"
    ACTIONED = "actioned"


class ModerationDecision(str, enum.Enum):
    DISMISS = "dismiss"
    ACTION = "action"


_ENUM = dict(native_enum=False, length=16)


class Flag(Base):
    __tablename__ = "flags"
    __table_args__ = (UniqueConstraint("photo_id", "reporter_id", name="uq_flag_photo_reporter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reason: Mapped[FlagReason] = mapped_column(Enum(FlagReason, **_ENUM), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[FlagStatus] = mapped_column(
        Enum(FlagStatus, **_ENUM), default=FlagStatus.PENDING, nullable=False, index=True
    )
    resolution: Mapped[FlagResolution | None] = mapped_column(
        Enum(FlagResolution, **_ENUM), nullable=True
    )
    resolved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    photo: Mapped["Photo"] = relationship(back_populates="flags")  # noqa: F821
    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])  # noqa: F821


class ModerationAction(Base):
    """Immutable audit row. Plain int refs so it outlives a deleted photo/flag."""

    __tablename__ = "moderation_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    flag_id: Mapped[int] = mapped_column(Integer, nullable=False)
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[ModerationDecision] = mapped_column(
        Enum(ModerationDecision, **_ENUM), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
