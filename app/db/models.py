from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)
    daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Per-user override for the daily delivery time, expressed as "HH:MM" in UTC.
    #: NULL means «use the system default» (env's DAILY_DELIVERY_TIME, in DAILY_DELIVERY_TIMEZONE).
    delivery_time_utc: Mapped[str | None] = mapped_column(String(5), nullable=True)
    #: Per-user override for daily question count. NULL = use env default.
    daily_questions_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: When True, the COLREGs trainer renders night-mode scenes (lights only).
    colregs_night_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    #: Comma-separated list of vessel-type codes the COLREGs picker will pull
    #: scenarios from. Empty = use default (all types). Codes match the
    #: `VesselType` enum values: sail / motor / fishing / nuc / ram.
    colregs_enabled_types: Mapped[str] = mapped_column(
        String(64), default="sail,motor,fishing,nuc,ram", nullable=False,
        server_default="sail,motor,fishing,nuc,ram",
    )
    #: While set to a future timestamp, daily deliveries are paused for
    #: this user. Year ≥ 9000 is the «paused forever» sentinel. NULL when
    #: the user has never paused (or has resumed).
    paused_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: One-time purchase (Telegram Stars) unlocking the per-day detailed
    #: statistics navigator. False until the user pays.
    detailed_stats_unlocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    answers: Mapped[list[QuestionAnswer]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class QuestionAnswer(Base):
    """A single answered question.

    Identity of a question = (trainer_key, entry_code). The same (user, trainer, entry)
    triple may appear multiple times if the user revisits the question. The latest row
    determines current state; "not asked yet" = no rows at all.
    """

    __tablename__ = "question_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    trainer_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # 64 chars — COLREGs scenario codes like «colregs_overtaking_ms_3» are
    # 22 chars; allow plenty of room for future subjects.
    entry_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: True when the user pressed «Показать ответ» — counted separately in
    #: stats, but still has `is_correct=False` so existing «review wrong
    #: answers» logic in the daily picker scoops up skipped questions too.
    is_skipped: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="answers")

    __table_args__ = (
        Index("ix_qa_user_trainer_entry", "user_id", "trainer_key", "entry_code"),
        Index("ix_qa_user_correct", "user_id", "is_correct"),
    )


class DailyDelivery(Base):
    """Tracks daily delivery runs to avoid duplicate sends within the same day."""

    __tablename__ = "daily_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delivered_on: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD in MSK
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "delivered_on", name="uq_user_day"),)


class DailyQuestion(Base):
    """One row per question planned for a user's daily batch.

    The full N-question batch is enqueued at delivery time; the bot then
    sends questions one at a time, waiting for an answer before releasing
    the next. Lets the chat stay clean instead of a wall of unanswered
    photos at 17:00.

    sent_at / answered_at semantics:
      both NULL          — pending, not yet sent
      sent_at set        — currently in flight, awaiting user's tap
      both set           — done; user already answered (or pressed Show
                           Answer, which counts as skipped)
    """

    __tablename__ = "daily_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delivered_on: Mapped[str] = mapped_column(String(10), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    trainer_key: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "delivered_on", "position", name="uq_dq_user_day_position"
        ),
        Index("ix_dq_user_inflight", "user_id", "sent_at", "answered_at"),
    )


class InlineMediaCache(Base):
    """Caches Telegram `file_id` for each flag/pennant.

    Inline mode can't take a local file — Telegram needs either a public URL
    or a `file_id` that the bot has already uploaded somewhere. We fill this
    table once via `/preload_inline` (which sends every image to the caller's
    DM, then stores `file_id` from the response), and reuse those file_ids
    for `InlineQueryResultCachedPhoto` from then on.
    """

    __tablename__ = "inline_media_cache"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
