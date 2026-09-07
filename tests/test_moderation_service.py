"""Service-layer tests for the moderation feature — written before the
implementation (Phase 3 TDD). Exercises flag creation, duplicate protection,
the queue, and decision semantics without going through HTTP."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import (
    Flag,
    FlagResolution,
    FlagStatus,
    ModerationAction,
    Photo,
    Thumbnail,
    ThumbnailStatus,
    User,
)
from app.services import moderation_service


@pytest.fixture
def make_user(db):
    def _make(email, *, is_admin=False):
        u = User(email=email, hashed_password=hash_password("password123"), is_admin=is_admin)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    return _make


@pytest.fixture
def make_photo(db):
    def _make(owner, caption="p"):
        photo = Photo(
            owner_id=owner.id,
            original_filename="p.png",
            content_type="image/png",
            size_bytes=10,
            width=4,
            height=4,
            storage_path="/tmp/p.png",
            caption=caption,
        )
        photo.thumbnail = Thumbnail(status=ThumbnailStatus.PENDING)
        db.add(photo)
        db.commit()
        db.refresh(photo)
        return photo

    return _make


def test_create_flag_persists_pending_flag(db, make_user, make_photo):
    owner = make_user("owner@example.com")
    photo = make_photo(owner)

    flag = moderation_service.create_flag(
        db, photo, reporter=owner, reason="spam", note="looks off"
    )

    assert flag.id is not None
    assert flag.status == FlagStatus.PENDING
    assert flag.reason.value == "spam"
    assert flag.reporter_id == owner.id


def test_duplicate_flag_by_same_reporter_is_rejected(db, make_user, make_photo):
    owner = make_user("owner@example.com")
    photo = make_photo(owner)
    moderation_service.create_flag(db, photo, reporter=owner, reason="spam", note=None)

    with pytest.raises(moderation_service.DuplicateFlagError):
        moderation_service.create_flag(db, photo, reporter=owner, reason="other", note="again")

    assert db.scalar(select(Flag).where(Flag.photo_id == photo.id).order_by(Flag.id)) is not None
    assert len(db.scalars(select(Flag)).all()) == 1


def test_invalid_reason_is_rejected(db, make_user, make_photo):
    owner = make_user("owner@example.com")
    photo = make_photo(owner)
    with pytest.raises(ValueError):
        moderation_service.create_flag(db, photo, reporter=owner, reason="not-a-reason", note=None)


def test_queue_lists_pending_flags_newest_first(db, make_user, make_photo):
    u1 = make_user("u1@example.com")
    u2 = make_user("u2@example.com")
    p1 = make_photo(u1)
    p2 = make_photo(u2)
    moderation_service.create_flag(db, p1, reporter=u1, reason="spam", note=None)
    moderation_service.create_flag(db, p2, reporter=u2, reason="nudity", note=None)

    items, total = moderation_service.list_queue(db, limit=10, offset=0)

    assert total == 2
    assert [f.photo_id for f in items] == [p2.id, p1.id]  # newest first


def test_dismiss_decision_resolves_only_that_flag(db, make_user, make_photo):
    admin = make_user("admin@example.com", is_admin=True)
    u1 = make_user("u1@example.com")
    photo = make_photo(u1)
    flag = moderation_service.create_flag(db, photo, reporter=u1, reason="spam", note=None)

    result = moderation_service.decide(db, flag.id, moderator=admin, decision="dismiss", note="ok")

    db.refresh(flag)
    assert flag.status == FlagStatus.RESOLVED
    assert flag.resolution == FlagResolution.DISMISSED
    assert flag.resolved_by_id == admin.id
    assert flag.resolved_at is not None
    assert db.get(Photo, photo.id) is not None  # photo kept
    assert db.scalar(select(ModerationAction).where(ModerationAction.flag_id == flag.id)) is not None
    assert result.status == FlagStatus.RESOLVED


def test_action_decision_deletes_photo_and_closes_sibling_flags(db, make_user, make_photo):
    admin = make_user("admin@example.com", is_admin=True)
    owner = make_user("owner@example.com")
    reporter2 = make_user("r2@example.com")
    photo = make_photo(owner)
    f1 = moderation_service.create_flag(db, photo, reporter=owner, reason="spam", note=None)
    moderation_service.create_flag(db, photo, reporter=reporter2, reason="nudity", note=None)

    action = moderation_service.decide(
        db, f1.id, moderator=admin, decision="action", note="violates policy"
    )

    assert db.get(Photo, photo.id) is None  # photo removed
    audit = db.scalars(select(ModerationAction).where(ModerationAction.photo_id == photo.id)).all()
    assert len(audit) == 1
    assert audit[0].decision.value == "action"
    assert audit[0].moderator_id == admin.id
    # flag rows cascade away with the photo; the audit is what persists
    assert db.scalars(select(Flag)).all() == []
    assert action.photo_id == photo.id


def test_decide_on_missing_flag_raises(db, make_user):
    admin = make_user("admin@example.com", is_admin=True)
    with pytest.raises(moderation_service.FlagNotFoundError):
        moderation_service.decide(db, 999999, moderator=admin, decision="dismiss", note=None)


def test_decide_twice_on_same_flag_raises(db, make_user, make_photo):
    admin = make_user("admin@example.com", is_admin=True)
    u1 = make_user("u1@example.com")
    photo = make_photo(u1)
    flag = moderation_service.create_flag(db, photo, reporter=u1, reason="spam", note=None)
    moderation_service.decide(db, flag.id, moderator=admin, decision="dismiss", note=None)

    with pytest.raises(moderation_service.FlagAlreadyResolvedError):
        moderation_service.decide(db, flag.id, moderator=admin, decision="action", note=None)
