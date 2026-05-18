"""initial schema — users, question_answers, daily_deliveries

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ru"),
        sa.Column("daily_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "question_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=32), nullable=False),
        sa.Column("trainer_key", sa.String(length=64), nullable=False),
        sa.Column("entry_code", sa.String(length=16), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "asked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_question_answers_user_id", "question_answers", ["user_id"])
    op.create_index(
        "ix_qa_user_trainer_entry",
        "question_answers",
        ["user_id", "trainer_key", "entry_code"],
    )
    op.create_index("ix_qa_user_correct", "question_answers", ["user_id", "is_correct"])

    op.create_table(
        "daily_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delivered_on", sa.String(length=10), nullable=False),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "delivered_on", name="uq_user_day"),
    )
    op.create_index("ix_daily_deliveries_user_id", "daily_deliveries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_deliveries_user_id", table_name="daily_deliveries")
    op.drop_table("daily_deliveries")
    op.drop_index("ix_qa_user_correct", table_name="question_answers")
    op.drop_index("ix_qa_user_trainer_entry", table_name="question_answers")
    op.drop_index("ix_question_answers_user_id", table_name="question_answers")
    op.drop_table("question_answers")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
