"""inline media cache

Revision ID: 0003_inline_cache
Revises: 0002_user_settings
Create Date: 2026-05-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_inline_cache"
down_revision: str | None = "0002_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inline_media_cache",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("file_id", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("inline_media_cache")
