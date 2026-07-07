"""Daily delivery scheduler with per-user schedules and per-question queue.

A single APScheduler job ticks every minute. For each user whose
effective UTC time matches the current minute, we make sure today's
batch is enqueued in `daily_questions` — exactly once per (user, day) —
and then send the next pending question if the user has no in-flight one.

The remaining questions stay queued; they're released one at a time
from the quiz answer handler (see `bot/handlers/quiz.py`).
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import session_scope
from app.i18n import t
from app.logger import get_logger
from app.repositories import daily_queue, users
from app.services.question_picker import pick_daily_batch
from app.services.quiz_engine import build_question_from_pick, send_question
from app.services.user_settings import (
    colregs_enabled_types,
    effective_count,
    effective_time_utc,
    is_paused,
)
from app.training.colregs.data import involved_types

logger = get_logger(__name__)


def _colregs_filter_fn(enabled: set[str]):
    def fn(trainer_key: str, entry_code: str) -> bool:
        if not entry_code.startswith("colregs_"):
            return True
        types_in_scene = {vt.value for vt in involved_types(entry_code)}
        return types_in_scene.issubset(enabled)

    return fn


async def _build_question_for_pick(
    user, trainer_key: str, entry_code: str
):
    """Prepare a question for daily delivery.

    Note about `night_mode`: the user's Settings toggle governs *self-check*
    only. Daily delivery deliberately ignores it and flips a fresh coin per
    question — the point of the daily practice is to keep the user sharp in
    both modes, day AND night, so they can't just disable one and never see
    it again.
    """
    opts: dict = {}
    if trainer_key.startswith("colregs."):
        opts["night_mode"] = random.choice([True, False])
    return build_question_from_pick(trainer_key, entry_code, user.language, **opts)


async def _send_next_for_user(bot: Bot, user_id: int, telegram_id: int) -> None:
    """Pull one question off this user's queue and send it. No-op when the
    queue is empty or the user already has something in flight.
    """
    async with session_scope() as session:
        if await daily_queue.in_flight(session, user_id) is not None:
            return
        row = await daily_queue.next_to_send(session, user_id)
        if row is None:
            return
        user = await users.get_by_telegram_id(session, telegram_id)
        if user is None:
            return

        question = await _build_question_for_pick(user, row.trainer_key, row.entry_code)
        prefix = t("daily.review_marker", user.language) if row.is_review else None
        try:
            await send_question(bot, telegram_id, question, prefix=prefix, mode="d")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "daily.send_failed",
                user_id=user_id,
                row_id=row.id,
                error=str(exc),
            )
            return
        await daily_queue.mark_sent(session, row)


async def release_next_after_answer(
    bot: Bot, user_id: int, telegram_id: int, trainer_key: str, entry_code: str
) -> bool:
    """Called from quiz handler when user answers a question in mode='d'.

    Marks the in-flight queue entry answered, then sends the next pending
    one (if any). Returns True if a new question was released.
    """
    async with session_scope() as session:
        answered = await daily_queue.mark_answered_by_question(
            session, user_id, trainer_key, entry_code
        )
        if answered is None:
            # Not a queued daily answer (regular interactive quiz) — ignore.
            return False
        day = answered.delivered_on
        last = await daily_queue.is_last_in_day(session, user_id, day)
        next_row = await daily_queue.next_to_send(session, user_id)
        user = await users.get_by_telegram_id(session, telegram_id)
        lang = user.language if user else "ru"

    if next_row is not None:
        await _send_next_for_user(bot, user_id, telegram_id)
        return True

    if last:
        try:
            await bot.send_message(chat_id=telegram_id, text=t("daily.footer", lang))
        except Exception:  # noqa: BLE001
            pass
    return False


async def _ensure_batch_for_user(
    bot: Bot, user_id: int, telegram_id: int, lang: str, count: int, day: str
) -> bool:
    """Enqueue today's batch if it isn't there yet. Returns True when freshly enqueued.

    Before enqueueing, drops any not-yet-sent rows from previous days —
    that's what caps the visible batch at exactly `count` even after the
    user missed several days (they get today's N, not N × missed_days).
    """
    async with session_scope() as session:
        # Backlog cleanup: never carry unsent rows across day boundaries.
        purged = await daily_queue.purge_pending_from_other_days(session, user_id, day)
        if purged:
            logger.info("daily.purged_backlog", user_id=user_id, dropped=purged)

        if await daily_queue.batch_exists(session, user_id, day):
            return False
        batch = await pick_daily_batch(session, user_id, count=count)
        picks = [(p.trainer_key, p.entry_code, p.is_review) for p in batch]
        if not picks:
            logger.info("daily.empty_batch", user_id=user_id)
            return False
        await daily_queue.enqueue_batch(session, user_id, day, picks)

    # Header carries a «⏸ Сделать паузу» button so users can defer daily
    # delivery in one tap from the top of the batch, without menu diving.
    from app.bot.keyboards import daily_header_keyboard

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=t("daily.header", lang, count=count),
            reply_markup=daily_header_keyboard(lang),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily.header_failed", user_id=user_id, error=str(exc))
        return False
    return True


async def tick(bot: Bot) -> None:
    """One scheduler tick — every minute. For users whose UTC time matches
    the current minute, enqueue today's batch and release the first question.
    """
    now_utc = datetime.now(pytz.UTC)
    today_utc = now_utc.date().isoformat()
    current_hm = now_utc.strftime("%H:%M")

    async with session_scope() as session:
        active = await users.all_active(session)
        targets = [
            (u.id, u.telegram_id, u.language, effective_count(u))
            for u in active
            if effective_time_utc(u) == current_hm and not is_paused(u, now_utc)
        ]

    if not targets:
        return

    logger.info("daily.tick_dispatch", users=len(targets), at_utc=current_hm)
    for user_id, telegram_id, lang, count in targets:
        try:
            await _ensure_batch_for_user(bot, user_id, telegram_id, lang, count, today_utc)
            await _send_next_for_user(bot, user_id, telegram_id)
            await asyncio.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            logger.exception("daily.user_failed", user_id=user_id, error=str(exc))


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=pytz.UTC)
    scheduler.add_job(
        tick,
        trigger=CronTrigger(minute="*", timezone=pytz.UTC),
        kwargs={"bot": bot},
        id="daily_tick",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
    )
    scheduler.start()
    logger.info("scheduler.started", mode="per_minute_utc_queue")
    return scheduler
