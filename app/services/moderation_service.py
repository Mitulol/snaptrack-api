"""Moderation domain logic: flag creation, the review queue, and decisions.

Kept free of FastAPI so the Phase 3 TDD tests can drive it directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import cache
from app.models import (
    Flag,
    FlagReason,
    FlagResolution,
    FlagStatus,
    ModerationAction,
    ModerationDecision,
    Photo,
    User,
)
from app.services import notification_service, photo_service
from app.storage import delete_photo_files


class DuplicateFlagError(Exception):
    """This reporter has already flagged this photo."""


class FlagNotFoundError(Exception):
    pass


class FlagAlreadyResolvedError(Exception):
    pass


def create_flag(
    db: Session, photo: Photo, *, reporter: User, reason: str, note: str | None
) -> Flag:
    reason_enum = FlagReason(reason)  # raises ValueError on a bad value
    flag = Flag(
        photo_id=photo.id,
        reporter_id=reporter.id,
        reason=reason_enum,
        note=note,
        status=FlagStatus.PENDING,
    )
    db.add(flag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateFlagError from exc
    db.refresh(flag)
    return flag


def list_queue(db: Session, *, limit: int, offset: int) -> tuple[list[Flag], int]:
    total = db.scalar(
        select(func.count()).select_from(Flag).where(Flag.status == FlagStatus.PENDING)
    )
    rows = db.scalars(
        select(Flag)
        .options(selectinload(Flag.photo), selectinload(Flag.reporter))
        .where(Flag.status == FlagStatus.PENDING)
        .order_by(Flag.created_at.desc(), Flag.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), int(total or 0)


def decide(
    db: Session, flag_id: int, *, moderator: User, decision: str, note: str | None
) -> Flag | ModerationAction:
    decision_enum = ModerationDecision(decision)  # ValueError on a bad value
    flag = db.get(Flag, flag_id)
    if flag is None:
        raise FlagNotFoundError
    if flag.status is not FlagStatus.PENDING:
        raise FlagAlreadyResolvedError

    action = ModerationAction(
        photo_id=flag.photo_id,
        flag_id=flag.id,
        moderator_id=moderator.id,
        decision=decision_enum,
        note=note,
    )
    db.add(action)

    if decision_enum is ModerationDecision.DISMISS:
        _resolve(flag, FlagResolution.DISMISSED, moderator)
        notes = _queue_notifications(db, [flag], "dismiss", note)
        db.commit()
        db.refresh(flag)
        _dispatch(notes)
        return flag

    # ACTION: close every pending flag on the photo, then delete the photo.
    now = datetime.now(timezone.utc)
    siblings = list(
        db.scalars(
            select(Flag).where(
                Flag.photo_id == flag.photo_id, Flag.status == FlagStatus.PENDING
            )
        )
    )
    for sibling in siblings:
        _resolve(sibling, FlagResolution.ACTIONED, moderator, now=now)
    db.flush()

    notes = _queue_notifications(db, siblings, "action", note)

    # A pending flag implies its photo still exists (FK), so this is never None.
    photo_id = flag.photo_id
    db.delete(db.get(Photo, photo_id))  # cascades the flag rows; the audit row stays
    db.flush()
    delete_photo_files(photo_id)
    cache.cache_delete(cache.photo_cache_key(photo_id))

    db.commit()
    db.refresh(action)
    _dispatch(notes)
    return action


def _queue_notifications(
    db: Session, flags: list[Flag], decision: str, moderator_note: str | None
) -> list[int]:
    """Create outbox rows for each affected reporter; return their ids.

    Runs inside the decision transaction — the rows commit atomically with the
    resolution, and the ids are handed to Celery only after that commit.
    """
    reporter_ids = {f.reporter_id for f in flags}
    emails = dict(
        db.execute(select(User.id, User.email).where(User.id.in_(reporter_ids))).all()
    )
    recipients = [
        (emails[f.reporter_id], f.photo_id, f.id)
        for f in flags
        if f.reporter_id in emails
    ]
    rows = notification_service.queue_moderation_notifications(
        db, recipients=recipients, decision=decision, moderator_note=moderator_note
    )
    db.flush()
    return [row.id for row in rows]


def _dispatch(notification_ids: list[int]) -> None:
    # Local import: keeps the Celery stack out of the import path for callers
    # that only need the pure service layer (the Phase 3 TDD tests).
    from app.workers.tasks import deliver_notification

    for nid in notification_ids:
        deliver_notification.delay(nid)


def _resolve(
    flag: Flag, resolution: FlagResolution, moderator: User, *, now: datetime | None = None
) -> None:
    flag.status = FlagStatus.RESOLVED
    flag.resolution = resolution
    flag.resolved_by_id = moderator.id
    flag.resolved_at = now or datetime.now(timezone.utc)


# Re-exported so routes can catch a single module's errors.
PhotoNotFoundError = photo_service.PhotoNotFoundError
