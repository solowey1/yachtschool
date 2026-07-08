"""add users.detailed_stats_unlocked — paid per-day statistics

Set to true after the user buys the detailed-statistics navigator with
Telegram Stars. NULL/false means the paywall is shown instead.

Revision ID: 0009_detailed_stats
Revises: 0008_user_pause
Create Date: 2026-07-08

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009_detailed_stats"
down_revision: str | None = "0008_user_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "detailed_stats_unlocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "detailed_stats_unlocked")
