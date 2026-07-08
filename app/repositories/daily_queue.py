"""Per-user queue of daily questions, sent one at a time.

The scheduler enqueues the full batch at delivery time; `next_to_send`
picks the lowest unsent position (across all days, in case yesterday's
batch was never fully answered). `on_user_answer` is called from the
quiz handler to mark the in-flight question answered.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyQuestion


async def purge_pending_from_other_days(
    session: AsyncSession, user_id: int, keep_day: str
) -> int:
    """Drop any unanswered rows from days ≠ `keep_day`.

    Cleans up both never-sent items (backlog) AND sent-but-never-answered
    ones (in-flight from a missed day). Answered rows stay for stats.

    If an orphaned in-flight message is answered later, quiz.on_answer's
    release_next_after_answer will silently no-op (no queue row matches);
    the answer is still recorded through record_and_format_result, so
    stats stay accurate.
    """
    stmt = (
        delete(DailyQuestion)
        .where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.delivered_on != keep_day,
            DailyQuestion.answered_at.is_(None),
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def batch_exists(session: AsyncSession, user_id: int, day: str) -> bool:
    res = await session.execute(
        select(DailyQuestion.id).where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.delivered_on == day,
        ).limit(1)
    )
    return res.first() is not None


async def enqueue_batch(
    session: AsyncSession,
    user_id: int,
    day: str,
    picks: list[tuple[str, str, bool]],
) -> None:
    """Insert N rows for today's batch. `picks` = [(trainer_key, entry_code, is_review), …]."""
    for i, (trainer_key, entry_code, is_review) in enumerate(picks, start=1):
        session.add(
            DailyQuestion(
                user_id=user_id,
                delivered_on=day,
                position=i,
                trainer_key=trainer_key,
                entry_code=entry_code,
                is_review=is_review,
            )
        )
    await session.flush()


async def in_flight(session: AsyncSession, user_id: int) -> DailyQuestion | None:
    """The user's currently-sent-but-unanswered daily question, or None."""
    res = await session.execute(
        select(DailyQuestion)
        .where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.sent_at.is_not(None),
            DailyQuestion.answered_at.is_(None),
        )
        .order_by(DailyQuestion.sent_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def next_to_send(session: AsyncSession, user_id: int) -> DailyQuestion | None:
    """The earliest queued daily question that hasn't been sent yet."""
    res = await session.execute(
        select(DailyQuestion)
        .where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.sent_at.is_(None),
        )
        .order_by(DailyQuestion.delivered_on.asc(), DailyQuestion.position.asc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def mark_sent(session: AsyncSession, row: DailyQuestion) -> None:
    row.sent_at = datetime.utcnow()
    await session.flush()


async def mark_answered_by_question(
    session: AsyncSession, user_id: int, trainer_key: str, entry_code: str
) -> DailyQuestion | None:
    """Find the latest in-flight queue entry matching this answer and mark it done.

    Returns the row updated, or None when the answered question wasn't part
    of any queue (e.g. an interactive quiz answer).
    """
    res = await session.execute(
        select(DailyQuestion)
        .where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.trainer_key == trainer_key,
            DailyQuestion.entry_code == entry_code,
            DailyQuestion.sent_at.is_not(None),
            DailyQuestion.answered_at.is_(None),
        )
        .order_by(DailyQuestion.sent_at.desc())
        .limit(1)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None
    row.answered_at = datetime.utcnow()
    await session.flush()
    return row


async def is_last_in_day(
    session: AsyncSession, user_id: int, day: str
) -> bool:
    """True when every queued row for this user/day has been answered."""
    res = await session.execute(
        select(DailyQuestion.id)
        .where(
            DailyQuestion.user_id == user_id,
            DailyQuestion.delivered_on == day,
            DailyQuestion.answered_at.is_(None),
        )
        .limit(1)
    )
    return res.first() is None
