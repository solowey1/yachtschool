"""add users.paused_until — daily-delivery pause

NULL means the user has never paused (or has resumed). A future timestamp
means «paused until then»; a year ≥ 9000 is the sentinel for «paused
forever» (chosen over a separate bool so the scheduler check stays a
single comparison against now_utc).

Revision ID: 0008_user_pause
Revises: 0007_daily_queue
Create Date: 2026-07-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_pause"
down_revision: str | None = "0007_daily_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "paused_until")
