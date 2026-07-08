"""user-level COLREGs trainer settings

Revision ID: 0004_colregs_user_settings
Revises: 0003_inline_cache
Create Date: 2026-05-19

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004_colregs_user_settings"
down_revision: str | None = "0003_inline_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "colregs_night_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "colregs_enabled_types",
            sa.String(length=64),
            nullable=False,
            server_default="sail,motor,fishing,nuc,ram",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "colregs_enabled_types")
    op.drop_column("users", "colregs_night_mode")
