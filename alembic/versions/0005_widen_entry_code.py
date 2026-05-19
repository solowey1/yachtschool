"""widen question_answers.entry_code from VARCHAR(16) to VARCHAR(64)

The original 16-char limit dated from when entry codes were single letters
(A..Z) or short pennant codes (N0..N9, S1..S3, AP). COLREGs scenario codes
like «colregs_overtaking_ms_3» are 22+ chars and were silently rejected
with `StringDataRightTruncationError` on every answer.

Revision ID: 0005_widen_entry_code
Revises: 0004_colregs_user_settings
Create Date: 2026-05-19

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_widen_entry_code"
down_revision: str | None = "0004_colregs_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "question_answers",
        "entry_code",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "question_answers",
        "entry_code",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
