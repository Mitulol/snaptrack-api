"""Shared test fixtures.

Environment is pinned *before* any ``app`` import so ``app.config.settings``
(instantiated at import time) picks up the test database / storage paths.
"""

from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Iterator

import pytest

_STORAGE = tempfile.mkdtemp(prefix="snaptrack-test-")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["PHOTO_STORAGE_DIR"] = _STORAGE
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import fakeredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app import cache  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.workers.celery_app import celery_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    else:
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config("alembic.ini"), "head")
    yield
    if settings.database_url.startswith("sqlite"):
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _celery_eager() -> None:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    cache.set_cache_client(fakeredis.FakeRedis(decode_responses=True))
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    cache.set_cache_client(None)


@pytest.fixture
def db() -> Iterator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_image():
    def _make(width: int = 800, height: int = 600, fmt: str = "PNG", color=(70, 130, 180)) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (width, height), color).save(buf, format=fmt)
        return buf.getvalue()

    return _make


@pytest.fixture
def auth_headers(client: TestClient):
    """Register + log in a user, returning ``Authorization`` headers.

    Call with no args for a default user, or pass an email for a second user.
    """

    def _headers(email: str = "user@example.com", password: str = "password123") -> dict:
        client.post("/auth/register", json={"email": email, "password": password})
        resp = client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _headers


@pytest.fixture
def admin_headers(client: TestClient, auth_headers):
    """Headers for a user with ``is_admin=True`` (flag flipped directly in the DB)."""
    from sqlalchemy import select

    from app.models import User

    def _headers(email: str = "admin@example.com") -> dict:
        headers = auth_headers(email)
        with SessionLocal() as s:
            user = s.scalar(select(User).where(User.email == email))
            user.is_admin = True
            s.commit()
        return headers

    return _headers
