"""Daily delivery scheduler with per-user schedules.

A single APScheduler job runs every minute. Each tick we look at all
active users, compute their effective send-time in UTC, and dispatch to any
whose time matches the current minute. The `daily_deliveries` table keeps
each (user, UTC-date) idempotent so a restart during a delivery window
doesn't double-send.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import session_scope
from app.i18n import t
from app.logger import get_logger
from app.repositories import history, users
from app.services.question_picker import pick_daily_batch
from app.services.quiz_engine import build_question_from_pick, send_question
from app.services.user_settings import effective_count, effective_time_utc

logger = get_logger(__name__)


async def deliver_daily_for_user(
    bot: Bot,
    user_id: int,
    telegram_id: int,
    lang: str,
    *,
    count: int,
    day,
) -> int:
    """Send today's batch to one user. Returns the number of questions actually sent."""
    async with session_scope() as session:
        was_inserted = await history.mark_delivered(session, user_id, day)
        if not was_inserted:
            logger.info(
                "daily.skip_already_delivered", user_id=user_id, day=day.isoformat()
            )
            return 0

        batch = await pick_daily_batch(session, user_id, count=count)

    if not batch:
        logger.info("daily.empty_batch", user_id=user_id)
        return 0

    try:
        await bot.send_message(chat_id=telegram_id, text=t("daily.header", lang))
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily.header_failed", user_id=user_id, error=str(exc))
        return 0

    sent = 0
    for pick in batch:
        try:
            question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
            prefix = t("daily.review_marker", lang) if pick.is_review else None
            await send_question(bot, telegram_id, question, prefix=prefix, mode="d")
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "daily.question_failed",
                user_id=user_id,
                trainer_key=pick.trainer_key,
                entry_code=pick.entry_code,
                error=str(exc),
            )

    try:
        await bot.send_message(chat_id=telegram_id, text=t("daily.footer", lang))
    except Exception:  # noqa: BLE001
        pass
    return sent


async def tick(bot: Bot) -> None:
    """One scheduler tick — dispatch to every user whose UTC time matches now."""
    now_utc = datetime.now(pytz.UTC)
    today_utc = now_utc.date()
    current_hm = now_utc.strftime("%H:%M")

    async with session_scope() as session:
        active = await users.all_active(session)
        targets = [
            (u.id, u.telegram_id, u.language, effective_count(u))
            for u in active
            if effective_time_utc(u) == current_hm
        ]

    if not targets:
        return

    logger.info("daily.tick_dispatch", users=len(targets), at_utc=current_hm)
    for user_id, telegram_id, lang, count in targets:
        try:
            await deliver_daily_for_user(
                bot, user_id, telegram_id, lang, count=count, day=today_utc
            )
            await asyncio.sleep(0.05)  # be polite to Telegram's rate limits
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
    logger.info("scheduler.started", mode="per_minute_utc")
    return scheduler
