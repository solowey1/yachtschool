"""add user delivery settings

Revision ID: 0002_user_settings
Revises: 0001_initial
Create Date: 2026-05-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_settings"
down_revision: str | None = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("delivery_time_utc", sa.String(length=5), nullable=True))
    op.add_column("users", sa.Column("daily_questions_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_questions_count")
    op.drop_column("users", "delivery_time_utc")
