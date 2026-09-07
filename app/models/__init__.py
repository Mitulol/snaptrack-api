"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.moderation import (
    Flag,
    FlagReason,
    FlagResolution,
    FlagStatus,
    ModerationAction,
    ModerationDecision,
)
from app.models.notification import Notification, NotificationKind, NotificationStatus
from app.models.photo import Photo
from app.models.thumbnail import Thumbnail, ThumbnailStatus
from app.models.user import User

__all__ = [
    "User",
    "Photo",
    "Thumbnail",
    "ThumbnailStatus",
    "Flag",
    "FlagReason",
    "FlagStatus",
    "FlagResolution",
    "ModerationAction",
    "ModerationDecision",
    "Notification",
    "NotificationKind",
    "NotificationStatus",
]
