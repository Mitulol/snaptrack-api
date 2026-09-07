from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationKind(str, enum.Enum):
    MODERATION_DECISION = "moderation_decision"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


_ENUM = dict(native_enum=False, length=32)


class Notification(Base):
    """Transactional-outbox row for an outbound message.

    Written in the same transaction as the moderation decision that triggers
    it, then delivered by the ``notifications.deliver`` Celery task. Photo /
    flag references are plain integers (no FK) because an ``action`` decision
    deletes both before the task runs.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind, **_ENUM), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    photo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flag_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, **_ENUM),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
