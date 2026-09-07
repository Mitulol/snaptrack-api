"""SQLAlchemy engine / session wiring.

The engine is built lazily from :data:`app.config.settings` so tests can point
``DATABASE_URL`` at SQLite (or a throwaway Postgres) before the first import
side effect. A single shared :class:`sessionmaker` is reused by the API request
dependency and by Celery tasks.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # In-memory SQLite needs a shared connection across threads for the
        # TestClient + Celery-eager path to see the same data.
        return {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    return {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
    }


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


if settings.database_url.startswith("sqlite"):
    # SQLite ignores ON DELETE CASCADE unless FK enforcement is switched on per
    # connection — do it so the test DB matches Postgres' referential behaviour.
    @event.listens_for(engine, "connect")
    def _sqlite_fk_pragma(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
