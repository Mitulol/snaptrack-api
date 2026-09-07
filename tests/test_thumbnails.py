"""Thumbnail worker tests. Celery runs eager (see conftest) so ``.delay()``
executes inline and the DB reflects the result by the time the request returns.
"""

from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Photo, Thumbnail, ThumbnailStatus
from app.storage import thumbnail_path
from app.workers.tasks import generate_thumbnail


def _upload(client, headers, image_bytes):
    files = {"file": ("pic.png", image_bytes, "image/png")}
    return client.post("/photos", headers=headers, files=files)


def test_thumbnail_becomes_ready_after_upload(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image(1000, 800)).json()["id"]

    resp = client.get(f"/photos/{pid}/thumbnail", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert max(body["width"], body["height"]) == 256
    assert body["attempts"] == 1


def test_thumbnail_file_is_served_when_ready(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image()).json()["id"]
    resp = client.get(f"/photos/{pid}/thumbnail/file", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert Path(thumbnail_path(pid)).exists()


def test_thumbnail_marked_failed_when_source_missing(client, auth_headers, make_image, db):
    headers = auth_headers()
    pid = _upload(client, headers, make_image()).json()["id"]

    # Simulate corruption: the original blob disappears before (re)processing.
    photo = db.scalar(select(Photo).where(Photo.id == pid))
    Path(photo.storage_path).unlink()
    thumb = db.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
    thumb.status = ThumbnailStatus.PENDING
    db.commit()

    generate_thumbnail.run(pid)

    with SessionLocal() as s:
        thumb = s.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
        assert thumb.status == ThumbnailStatus.FAILED
        assert thumb.error


def test_thumbnail_task_noop_for_missing_photo():
    result = generate_thumbnail.run(424242)
    assert result["status"] == "missing"


def test_thumbnail_file_conflict_before_ready(client, auth_headers, make_image, db):
    headers = auth_headers()
    pid = _upload(client, headers, make_image()).json()["id"]
    thumb = db.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
    thumb.status = ThumbnailStatus.PENDING
    db.commit()

    resp = client.get(f"/photos/{pid}/thumbnail/file", headers=headers)
    assert resp.status_code == 409
