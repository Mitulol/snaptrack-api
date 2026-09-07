"""moderation: flags + moderation_actions

Revision ID: 0002_moderation
Revises: 0001_initial
Create Date: 2026-09-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_moderation"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("photo_id", "reporter_id", name="uq_flag_photo_reporter"),
    )
    op.create_index("ix_flags_photo_id", "flags", ["photo_id"])
    op.create_index("ix_flags_reporter_id", "flags", ["reporter_id"])
    op.create_index("ix_flags_status", "flags", ["status"])

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("flag_id", sa.Integer(), nullable=False),
        sa.Column("moderator_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_moderation_actions_photo_id", "moderation_actions", ["photo_id"])


def downgrade() -> None:
    op.drop_table("moderation_actions")
    op.drop_index("ix_flags_status", table_name="flags")
    op.drop_index("ix_flags_reporter_id", table_name="flags")
    op.drop_index("ix_flags_photo_id", table_name="flags")
    op.drop_table("flags")
