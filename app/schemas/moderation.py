from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.moderation import (
    FlagReason,
    FlagResolution,
    FlagStatus,
    ModerationDecision,
)


class FlagCreate(BaseModel):
    reason: FlagReason
    note: str | None = Field(default=None, max_length=2048)


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_id: int
    reporter_id: int
    reason: FlagReason
    note: str | None
    status: FlagStatus
    resolution: FlagResolution | None
    resolved_by_id: int | None
    resolved_at: datetime | None
    created_at: datetime


class QueuePhoto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    caption: str | None
    created_at: datetime


class QueueItem(FlagOut):
    photo: QueuePhoto | None = None
    reporter_email: str | None = None


class ModerationQueue(BaseModel):
    items: list[QueueItem]
    total: int
    limit: int
    offset: int


class DecisionCreate(BaseModel):
    decision: ModerationDecision
    note: str | None = Field(default=None, max_length=2048)


class ModerationActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_id: int
    flag_id: int
    moderator_id: int | None
    decision: ModerationDecision
    note: str | None
    created_at: datetime
