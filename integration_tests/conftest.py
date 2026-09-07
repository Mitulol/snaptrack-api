"""Integration suite: the real app against real Postgres + Redis, spun up by
pytest-docker. Kept outside ``tests/`` so it does not inherit that package's
SQLite/fakeredis conftest.

Nothing imports ``app`` at module load — env has to be pointed at the containers
first, which only happens once ``integration_stack`` (session, autouse) runs.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def docker_compose_file() -> str:
    return str(Path(__file__).parent / "docker-compose.yml")


def _pg_ready(dsn: str) -> bool:
    try:
        psycopg2.connect(dsn).close()
        return True
    except psycopg2.OperationalError:
        return False


@pytest.fixture(scope="session", autouse=True)
def integration_stack(docker_ip, docker_services) -> Iterator[None]:
    pg_port = docker_services.port_for("postgres", 5432)
    redis_port = docker_services.port_for("redis", 6379)
    dsn = f"host={docker_ip} port={pg_port} user=itest password=itest dbname=itest"
    docker_services.wait_until_responsive(timeout=60.0, pause=1.0, check=lambda: _pg_ready(dsn))

    os.environ.update(
        ENVIRONMENT="test",
        DATABASE_URL=f"postgresql+psycopg2://itest:itest@{docker_ip}:{pg_port}/itest",
        REDIS_URL=f"redis://{docker_ip}:{redis_port}/0",
        CELERY_BROKER_URL=f"redis://{docker_ip}:{redis_port}/1",
        CELERY_RESULT_BACKEND=f"redis://{docker_ip}:{redis_port}/2",
        PHOTO_STORAGE_DIR=tempfile.mkdtemp(prefix="snaptrack-itest-"),
        JWT_SECRET_KEY="itest-secret",
    )

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    from app.workers.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    yield


@pytest.fixture(autouse=True)
def _clean(integration_stack) -> Iterator[None]:
    from sqlalchemy import text

    from app.database import engine

    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, photos, thumbnails, flags, moderation_actions, "
                "notifications RESTART IDENTITY CASCADE"
            )
        )
    try:
        from app.cache import get_cache_client

        get_cache_client().flushdb()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def client(integration_stack) -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(integration_stack) -> Iterator:
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def make_png():
    def _make() -> bytes:
        import zlib
        import struct

        w = h = 32
        raw = b"".join(b"\x00" + b"\x46\x82\xb4" * w for _ in range(h))

        def chunk(t: bytes, d: bytes) -> bytes:
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )

    return _make


@pytest.fixture
def register(client):
    def _register(email: str, *, admin: bool = False) -> dict:
        client.post("/auth/register", json={"email": email, "password": "password123"})
        if admin:
            from sqlalchemy import text

            from app.database import engine

            with engine.begin() as conn:
                conn.execute(text("UPDATE users SET is_admin = true WHERE email = :e"), {"e": email})
        token = client.post(
            "/auth/login", json={"email": email, "password": "password123"}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
