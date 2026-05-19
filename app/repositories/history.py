from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyDelivery, QuestionAnswer


async def record_answer(
    session: AsyncSession,
    *,
    user_id: int,
    subject: str,
    topic: str,
    trainer_key: str,
    entry_code: str,
    is_correct: bool,
) -> None:
    session.add(
        QuestionAnswer(
            user_id=user_id,
            subject=subject,
            topic=topic,
            trainer_key=trainer_key,
            entry_code=entry_code,
            is_correct=is_correct,
        )
    )
    await session.flush()


async def asked_combinations(
    session: AsyncSession, user_id: int
) -> set[tuple[str, str]]:
    """Return the set of (trainer_key, entry_code) the user has already been asked."""
    res = await session.execute(
        select(QuestionAnswer.trainer_key, QuestionAnswer.entry_code)
        .where(QuestionAnswer.user_id == user_id)
        .distinct()
    )
    return {(row.trainer_key, row.entry_code) for row in res.all()}


async def latest_wrong_answers(
    session: AsyncSession, user_id: int, limit: int = 50
) -> list[tuple[str, str]]:
    """Most-recent (trainer_key, entry_code) pairs where the user was wrong.

    We pick the latest row per (trainer, entry) combination — if the user has
    since answered the same question correctly, we don't consider it as needing
    review.
    """
    subq = (
        select(
            QuestionAnswer.trainer_key,
            QuestionAnswer.entry_code,
            QuestionAnswer.is_correct,
            QuestionAnswer.asked_at,
            func.row_number()
            .over(
                partition_by=(QuestionAnswer.trainer_key, QuestionAnswer.entry_code),
                order_by=QuestionAnswer.asked_at.desc(),
            )
            .label("rn"),
        )
        .where(QuestionAnswer.user_id == user_id)
        .subquery()
    )
    res = await session.execute(
        select(subq.c.trainer_key, subq.c.entry_code)
        .where(subq.c.rn == 1, subq.c.is_correct.is_(False))
        .order_by(subq.c.asked_at.desc())
        .limit(limit)
    )
    return [(row.trainer_key, row.entry_code) for row in res.all()]


_correct_sum = func.sum(case((QuestionAnswer.is_correct, 1), else_=0))


async def topic_stats(
    session: AsyncSession, user_id: int
) -> list[tuple[str, int, int]]:
    """Per-topic (topic, total_answered, correct)."""
    res = await session.execute(
        select(
            QuestionAnswer.topic,
            func.count().label("total"),
            _correct_sum.label("correct"),
        )
        .where(QuestionAnswer.user_id == user_id)
        .group_by(QuestionAnswer.topic)
    )
    return [(r.topic, int(r.total), int(r.correct or 0)) for r in res.all()]


async def subject_topic_stats(
    session: AsyncSession, user_id: int
) -> list[tuple[str, str, int, int]]:
    """Per-(subject, topic) breakdown — used to group the stats view by subject."""
    res = await session.execute(
        select(
            QuestionAnswer.subject,
            QuestionAnswer.topic,
            func.count().label("total"),
            _correct_sum.label("correct"),
        )
        .where(QuestionAnswer.user_id == user_id)
        .group_by(QuestionAnswer.subject, QuestionAnswer.topic)
    )
    return [
        (r.subject, r.topic, int(r.total), int(r.correct or 0)) for r in res.all()
    ]


async def overall_stats(session: AsyncSession, user_id: int) -> tuple[int, int]:
    """Return (total_answers, correct_answers)."""
    res = await session.execute(
        select(
            func.count().label("total"),
            _correct_sum.label("correct"),
        ).where(QuestionAnswer.user_id == user_id)
    )
    row = res.one()
    return int(row.total or 0), int(row.correct or 0)


async def mark_delivered(session: AsyncSession, user_id: int, day: date) -> bool:
    """Idempotently record a daily delivery. Returns True if a new row was inserted."""
    stmt = (
        pg_insert(DailyDelivery)
        .values(user_id=user_id, delivered_on=day.isoformat())
        .on_conflict_do_nothing(index_elements=["user_id", "delivered_on"])
        .returning(DailyDelivery.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None
