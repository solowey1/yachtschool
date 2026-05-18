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
    entry_code: Mapped[str] = mapped_column(String(16), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
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
