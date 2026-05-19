"""queue daily questions so they're sent one at a time

The previous behaviour dumped all N daily questions into the chat at
delivery time. Users found it overwhelming and stopped engaging. This
table holds the planned batch; the scheduler sends position 1 only,
and each answered question triggers the next one to be sent.

Revision ID: 0007_daily_queue
Revises: 0006_skipped_answers
Create Date: 2026-05-19

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_daily_queue"
down_revision: str | None = "0006_skipped_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delivered_on", sa.String(length=10), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("trainer_key", sa.String(length=64), nullable=False),
        sa.Column("entry_code", sa.String(length=64), nullable=False),
        sa.Column(
            "is_review", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "delivered_on", "position", name="uq_dq_user_day_position"
        ),
    )
    op.create_index("ix_daily_questions_user_id", "daily_questions", ["user_id"])
    op.create_index(
        "ix_dq_user_inflight",
        "daily_questions",
        ["user_id", "sent_at", "answered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dq_user_inflight", table_name="daily_questions")
    op.drop_index("ix_daily_questions_user_id", table_name="daily_questions")
    op.drop_table("daily_questions")
