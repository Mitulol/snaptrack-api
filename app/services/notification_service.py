"""Moderation notifications: build outbox rows, then deliver them.

``queue_moderation_notifications`` runs inside the moderation-decision
transaction (so a notification is never lost to a crash between the DB commit
and enqueueing the job). ``deliver`` is what the Celery task calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Notification, NotificationKind, NotificationStatus
from app.services.mailer import NotificationDeliveryError, deliver_email

logger = logging.getLogger("snaptrack.notifications")

_SUBJECT = {
    "dismiss": "Your report was reviewed — no action taken",
    "action": "Your report was reviewed — the photo was removed",
}
_OUTCOME = {
    "dismiss": (
        "A moderator reviewed the photo you reported and decided it does not "
        "violate our content policy. The photo stays up and your report is "
        "now closed."
    ),
    "action": (
        "A moderator reviewed the photo you reported, agreed it violates our "
        "content policy, and removed it. Thanks for helping keep SnapTrack safe."
    ),
}


class NotificationMissing(Exception):
    """The referenced notification row is gone."""


def render_moderation_message(decision: str, photo_id: int, moderator_note: str | None) -> tuple[str, str]:
    body = f"{_OUTCOME[decision]}\n\nPhoto: #{photo_id}"
    if moderator_note:
        body += f"\nModerator note: {moderator_note}"
    return _SUBJECT[decision], body


def queue_moderation_notifications(
    db: Session,
    *,
    recipients: list[tuple[str, int, int]],
    decision: str,
    moderator_note: str | None,
) -> list[Notification]:
    """Create (but do not commit) one pending row per recipient.

    ``recipients`` is a list of ``(email, photo_id, flag_id)``. The caller
    commits as part of the decision transaction, then dispatches by id.
    """
    rows: list[Notification] = []
    for email, photo_id, flag_id in recipients:
        subject, body = render_moderation_message(decision, photo_id, moderator_note)
        row = Notification(
            recipient_email=email,
            kind=NotificationKind.MODERATION_DECISION,
            subject=subject,
            body=body,
            photo_id=photo_id,
            flag_id=flag_id,
            status=NotificationStatus.PENDING,
        )
        db.add(row)
        rows.append(row)
    return rows


def deliver(db: Session, notification_id: int) -> Notification:
    """Attempt delivery of one notification. Idempotent for already-sent rows.

    Raises :class:`NotificationMissing` if the row is gone, or
    :class:`~app.services.mailer.NotificationDeliveryError` on a retryable
    failure (the row is left ``failed`` with the error recorded).
    """
    row = db.get(Notification, notification_id)
    if row is None:
        raise NotificationMissing(str(notification_id))
    if row.status is NotificationStatus.SENT:
        return row

    row.attempts += 1
    try:
        deliver_email(to=row.recipient_email, subject=row.subject, body=row.body)
    except NotificationDeliveryError as exc:
        row.status = NotificationStatus.FAILED
        row.error = str(exc)[:1024]
        db.commit()
        logger.warning("notification %s delivery failed: %s", notification_id, exc)
        raise

    row.status = NotificationStatus.SENT
    row.sent_at = datetime.now(timezone.utc)
    row.error = None
    db.commit()
    return row
