"""Async work: thumbnail generation.

Split out from the image helpers so the Celery wiring (sessions, retries, cache
invalidation) is what this module owns and tests target.
"""

from __future__ import annotations

import logging

from PIL import UnidentifiedImageError
from sqlalchemy import select

from app import cache
from app.config import settings
from app.database import SessionLocal
from app.models import Photo, Thumbnail, ThumbnailStatus
from app.services import notification_service
from app.services.images import InvalidImageError, make_thumbnail
from app.services.mailer import NotificationDeliveryError
from app.storage import thumbnail_path
from app.workers.celery_app import celery_app

logger = logging.getLogger("snaptrack.worker")

# Errors that a retry cannot fix — fail fast instead of burning the retry budget.
PERMANENT_ERRORS = (InvalidImageError, UnidentifiedImageError, FileNotFoundError)


@celery_app.task(bind=True, name="thumbnails.generate", max_retries=settings.thumbnail_task_max_retries)
def generate_thumbnail(self, photo_id: int) -> dict:
    db = SessionLocal()
    try:
        thumb = db.scalar(select(Thumbnail).where(Thumbnail.photo_id == photo_id))
        photo = db.get(Photo, photo_id)
        if photo is None or thumb is None:
            logger.warning("generate_thumbnail: photo %s vanished", photo_id)
            return {"photo_id": photo_id, "status": "missing"}

        thumb.status = ThumbnailStatus.PROCESSING
        thumb.attempts += 1
        db.commit()

        try:
            width, height = make_thumbnail(
                photo.storage_path, thumbnail_path(photo_id), settings.thumbnail_max_edge
            )
        except PERMANENT_ERRORS as exc:
            thumb.status = ThumbnailStatus.FAILED
            thumb.error = str(exc)[:1024]
            db.commit()
            _invalidate(photo_id)
            logger.error("generate_thumbnail: permanent failure for %s: %s", photo_id, exc)
            return {"photo_id": photo_id, "status": "failed", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - transient; retry with backoff
            thumb.status = ThumbnailStatus.PENDING
            thumb.error = str(exc)[:1024]
            db.commit()
            _invalidate(photo_id)
            if self.request.retries >= self.max_retries:
                thumb.status = ThumbnailStatus.FAILED
                db.commit()
                _invalidate(photo_id)
                return {"photo_id": photo_id, "status": "failed", "error": str(exc)}
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

        thumb.status = ThumbnailStatus.READY
        thumb.storage_path = str(thumbnail_path(photo_id))
        thumb.width, thumb.height = width, height
        thumb.error = None
        db.commit()
        _invalidate(photo_id)
        return {"photo_id": photo_id, "status": "ready", "width": width, "height": height}
    finally:
        db.close()


def _invalidate(photo_id: int) -> None:
    cache.cache_delete(cache.photo_cache_key(photo_id))


@celery_app.task(
    bind=True,
    name="notifications.deliver",
    max_retries=settings.notification_task_max_retries,
    default_retry_delay=10,
)
def deliver_notification(self, notification_id: int) -> dict:
    """Deliver one outbox row (see ``app.services.notification_service``).

    Enqueued by ``moderation_service.decide`` after the decision commits.
    """
    db = SessionLocal()
    try:
        try:
            row = notification_service.deliver(db, notification_id)
        except notification_service.NotificationMissing:
            logger.warning("deliver_notification: row %s vanished", notification_id)
            return {"notification_id": notification_id, "status": "missing"}
        except NotificationDeliveryError as exc:
            if self.request.retries >= self.max_retries:
                logger.error(
                    "deliver_notification: giving up on %s after %s tries: %s",
                    notification_id, self.request.retries, exc,
                )
                return {"notification_id": notification_id, "status": "failed", "error": str(exc)}
            raise self.retry(exc=exc)
        return {
            "notification_id": notification_id,
            "status": row.status.value,
            "attempts": row.attempts,
        }
    finally:
        db.close()
