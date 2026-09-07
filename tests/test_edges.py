"""Edge / failure-path coverage: auth corner cases, readiness degradation,
upload limits, and the worker's transient-retry path."""

import fakeredis
import redis
from sqlalchemy import select

from app import cache
from app.api.routes import health, photos
from app.config import settings
from app.database import SessionLocal
from app.models import Thumbnail, ThumbnailStatus, User
from app.services import images
from app.workers.tasks import generate_thumbnail


def _upload(client, headers, make_image):
    files = {"file": ("pic.png", make_image(), "image/png")}
    return client.post("/photos", headers=headers, files=files)


def test_is_testing_flag():
    assert settings.is_testing is True


def test_empty_bearer_is_401(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer "}).status_code == 401


def test_valid_token_for_deleted_user_is_401(client, auth_headers):
    headers = auth_headers("gone@example.com")
    with SessionLocal() as s:
        s.delete(s.scalar(select(User).where(User.email == "gone@example.com")))
        s.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_inactive_user_cannot_authenticate(client, auth_headers):
    headers = auth_headers("inactive@example.com")
    with SessionLocal() as s:
        u = s.scalar(select(User).where(User.email == "inactive@example.com"))
        u.is_active = False
        s.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401
    login = client.post(
        "/auth/login", json={"email": "inactive@example.com", "password": "password123"}
    )
    assert login.status_code == 403


def test_readyz_returns_503_when_redis_unreachable(client, monkeypatch):
    class Down(fakeredis.FakeRedis):
        def ping(self):
            raise redis.ConnectionError("no route to redis")

    monkeypatch.setattr(health, "get_cache_client", lambda: Down())
    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
    assert resp.json()["checks"]["redis"].startswith("error")


def test_readyz_returns_503_when_database_unreachable(client):
    from app.database import get_db
    from app.main import app

    class BrokenSession:
        def execute(self, *_a, **_k):
            raise RuntimeError("connection refused")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        resp = client.get("/readyz")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 503
    assert resp.json()["checks"]["database"].startswith("error")


def test_upload_rejects_oversized_file(client, auth_headers, make_image, monkeypatch):
    monkeypatch.setattr(photos, "MAX_UPLOAD_BYTES", 10)
    resp = _upload(client, auth_headers(), make_image)
    assert resp.status_code == 413


def test_thumbnail_endpoints_404_for_non_owner(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    pid = _upload(client, alice, make_image).json()["id"]
    assert client.get(f"/photos/{pid}/thumbnail", headers=bob).status_code == 404
    assert client.get(f"/photos/{pid}/thumbnail/file", headers=bob).status_code == 404
    assert client.get(f"/photos/{pid}/file", headers=bob).status_code == 404


def test_cache_delete_noop_without_keys():
    cache.cache_delete()  # must not raise


def test_list_photos_rejects_absurd_offset(client, auth_headers):
    # A huge offset used to overflow Postgres bigint -> unhandled 500.
    resp = client.get("/photos?offset=999999999999999999999", headers=auth_headers())
    assert resp.status_code == 422


def test_405_allow_header_lists_every_method_on_the_path(client, auth_headers):
    resp = client.request("PUT", "/photos/1", headers=auth_headers())
    assert resp.status_code == 405
    allowed = {m.strip() for m in resp.headers["allow"].split(",")}
    assert {"GET", "PATCH", "DELETE"} <= allowed


def test_405_allow_header_on_collection(client, auth_headers):
    resp = client.request("DELETE", "/photos", headers=auth_headers())
    assert resp.status_code == 405
    allowed = {m.strip() for m in resp.headers["allow"].split(",")}
    assert {"GET", "POST"} <= allowed


def test_cache_client_is_lazily_constructed():
    cache.set_cache_client(None)
    try:
        assert isinstance(cache.get_cache_client(), redis.Redis)
    finally:
        cache.set_cache_client(fakeredis.FakeRedis(decode_responses=True))


def test_engine_kwargs_differ_by_backend():
    from app.database import _engine_kwargs

    assert "poolclass" in _engine_kwargs("sqlite:///:memory:")
    pg = _engine_kwargs("postgresql+psycopg2://u:p@localhost/db")
    assert pg["pool_pre_ping"] is True and pg["pool_size"] == 10


def test_worker_retries_transient_error_then_fails(client, auth_headers, make_image, monkeypatch):
    headers = auth_headers()
    pid = _upload(client, headers, make_image).json()["id"]
    with SessionLocal() as s:
        t = s.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
        t.status = ThumbnailStatus.PENDING
        s.commit()

    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        raise RuntimeError("disk hiccup")

    monkeypatch.setattr("app.workers.tasks.make_thumbnail", flaky)
    result = generate_thumbnail.apply(args=[pid])

    assert result.result["status"] == "failed"
    assert calls["n"] == settings.thumbnail_task_max_retries + 1  # initial + retries
    with SessionLocal() as s:
        t = s.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
        assert t.status == ThumbnailStatus.FAILED


def test_probe_permanent_error_is_not_retried(client, auth_headers, make_image, monkeypatch):
    headers = auth_headers()
    pid = _upload(client, headers, make_image).json()["id"]
    with SessionLocal() as s:
        t = s.scalar(select(Thumbnail).where(Thumbnail.photo_id == pid))
        t.status = ThumbnailStatus.PENDING
        s.commit()

    calls = {"n": 0}

    def permanent(*_a, **_k):
        calls["n"] += 1
        raise images.InvalidImageError("corrupt")

    monkeypatch.setattr("app.workers.tasks.make_thumbnail", permanent)
    generate_thumbnail.apply(args=[pid])
    assert calls["n"] == 1  # no retries burned on a permanent error
