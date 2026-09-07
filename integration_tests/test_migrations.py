"""Round-trip every Alembic migration against real Postgres."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_CFG = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))


def test_downgrade_to_base_then_upgrade_head(integration_stack):
    from sqlalchemy import inspect

    from app.database import engine

    command.downgrade(_CFG, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    command.upgrade(_CFG, "head")
    tables = set(inspect(engine).get_table_names())
    assert {"users", "photos", "thumbnails", "flags", "moderation_actions"} <= tables


def test_head_matches_orm_metadata(integration_stack):
    """No pending model changes the migrations don't cover."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.database import Base, engine
    from app import models  # noqa: F401  (registers tables)

    command.upgrade(_CFG, "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"ORM and migrations diverge: {diff}"
