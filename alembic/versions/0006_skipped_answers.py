"""add is_skipped flag to question_answers

Tracks «Показать ответ» presses separately from wrong answers.
Skipped attempts still have is_correct=false so the existing review-pool
logic keeps treating them as «to be re-asked» — only the stats screen
differentiates correct / wrong / skipped.

Revision ID: 0006_skipped_answers
Revises: 0005_widen_entry_code
Create Date: 2026-05-19

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006_skipped_answers"
down_revision: str | None = "0005_widen_entry_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "question_answers",
        sa.Column(
            "is_skipped",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("question_answers", "is_skipped")
