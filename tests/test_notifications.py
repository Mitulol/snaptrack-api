"""Moderation-notification outbox: the mailer backends, the service, and the
Celery delivery task. Celery runs eager (see conftest)."""

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Notification, NotificationKind, NotificationStatus
from app.services import mailer, notification_service
from app.workers.tasks import deliver_notification


@pytest.fixture
def make_pending(db):
    """Persist and commit one pending notification row; return its id."""

    def _make(email="reporter@example.com", *, photo_id=1, flag_id=1):
        row = Notification(
            recipient_email=email,
            kind=NotificationKind.MODERATION_DECISION,
            subject="s",
            body="b",
            photo_id=photo_id,
            flag_id=flag_id,
            status=NotificationStatus.PENDING,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id

    return _make


@pytest.fixture(autouse=True)
def _console_backend(monkeypatch):
    monkeypatch.setattr(settings, "notification_backend", "console")
    yield


# --- mailer --------------------------------------------------------------

def test_console_backend_returns_marker():
    assert mailer.deliver_email(to="a@b.com", subject="hi", body="body") == "console"


def test_file_backend_writes_an_eml(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "notification_backend", "file")
    monkeypatch.setattr(settings, "notification_mail_dir", str(tmp_path))

    path = mailer.deliver_email(to="rcpt@example.com", subject="Removed", body="hello")

    written = tmp_path / path.split("/")[-1]
    assert written.exists()
    raw = written.read_text()
    assert "To: rcpt@example.com" in raw
    assert "Subject: Removed" in raw
    assert "hello" in raw


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr(settings, "notification_backend", "smoke-signals")
    with pytest.raises(mailer.NotificationDeliveryError):
        mailer.deliver_email(to="a@b.com", subject="x", body="y")


def test_file_backend_wraps_write_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "notification_backend", "file")
    monkeypatch.setattr(settings, "notification_mail_dir", str(tmp_path))

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.write_bytes", boom)
    with pytest.raises(mailer.NotificationDeliveryError):
        mailer.deliver_email(to="a@b.com", subject="x", body="y")


# --- notification_service ------------------------------------------------

@pytest.mark.parametrize("decision", ["dismiss", "action"])
def test_render_message_covers_both_decisions(decision):
    subject, body = notification_service.render_moderation_message(decision, 7, "be nice")
    assert subject
    assert "#7" in body
    assert "Moderator note: be nice" in body


def test_render_message_without_note():
    _, body = notification_service.render_moderation_message("dismiss", 3, None)
    assert "Moderator note" not in body


def test_queue_returns_empty_for_no_recipients(db):
    assert notification_service.queue_moderation_notifications(
        db, recipients=[], decision="dismiss", moderator_note=None
    ) == []


def test_deliver_marks_row_sent(db, make_pending):
    nid = make_pending()
    row = notification_service.deliver(db, nid)
    assert row.status is NotificationStatus.SENT
    assert row.sent_at is not None
    assert row.attempts == 1


def test_deliver_is_idempotent_for_sent_rows(db, make_pending):
    nid = make_pending()
    notification_service.deliver(db, nid)
    again = notification_service.deliver(SessionLocal(), nid)
    assert again.status is NotificationStatus.SENT
    assert again.attempts == 1  # not re-incremented


def test_deliver_missing_row_raises(db):
    with pytest.raises(notification_service.NotificationMissing):
        notification_service.deliver(db, 999999)


def test_deliver_records_failure(db, make_pending, monkeypatch):
    monkeypatch.setattr(settings, "notification_backend", "nope")
    nid = make_pending()
    with pytest.raises(mailer.NotificationDeliveryError):
        notification_service.deliver(db, nid)

    with SessionLocal() as s:
        row = s.get(Notification, nid)
        assert row.status is NotificationStatus.FAILED
        assert "nope" in row.error


# --- deliver_notification task ------------------------------------------

def test_task_delivers_pending_row(make_pending):
    nid = make_pending()
    result = deliver_notification.run(nid)
    assert result == {"notification_id": nid, "status": "sent", "attempts": 1}


def test_task_reports_missing_row():
    assert deliver_notification.run(123456)["status"] == "missing"


def test_task_retries_then_gives_up(make_pending, monkeypatch):
    monkeypatch.setattr(settings, "notification_backend", "nope")
    monkeypatch.setattr(deliver_notification, "max_retries", 1)
    nid = make_pending()

    deliver_notification.apply(args=[nid])  # eager; swallows the final raise

    with SessionLocal() as s:
        row = s.get(Notification, nid)
        assert row.status is NotificationStatus.FAILED
        assert row.attempts == 2  # initial try + one retry


def test_task_dispatched_by_a_moderation_decision(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    owner = auth_headers("owner@example.com")
    files = {"file": ("p.png", make_image(), "image/png")}
    pid = client.post("/photos", headers=owner, files=files).json()["id"]
    flag_id = client.post(f"/photos/{pid}/flag", headers=owner, json={"reason": "spam"}).json()["id"]

    client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "dismiss"})

    with SessionLocal() as s:
        rows = s.scalars(select(Notification)).all()
    assert len(rows) == 1
    assert rows[0].recipient_email == "owner@example.com"
    assert rows[0].status is NotificationStatus.SENT
    assert rows[0].photo_id == pid
