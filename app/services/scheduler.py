"""Daily delivery scheduler — sends N questions to each opted-in user at the configured time."""

from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.config import settings
from app.db.session import session_scope
from app.i18n import t
from app.logger import get_logger
from app.repositories import history, users
from app.services.question_picker import PickedQuestion, pick_daily_batch
from app.services.quiz_engine import build_question_from_pick, send_question

logger = get_logger(__name__)


async def deliver_daily_for_user(
    bot: Bot, user_id: int, telegram_id: int, lang: str
) -> int:
    """Send today's batch to one user. Returns the number of questions actually sent."""

    tz = timezone(settings.daily_delivery_timezone)
    today_local = datetime.now(tz).date()

    async with session_scope() as session:
        was_inserted = await history.mark_delivered(session, user_id, today_local)
        if not was_inserted:
            logger.info("daily.skip_already_delivered", user_id=user_id, day=today_local.isoformat())
            return 0

        batch = await pick_daily_batch(session, user_id)

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
            # mode="d" so the answer keyboard omits the «Next question» button — the
            # next daily question is already further down in the chat.
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


async def deliver_daily_all(bot: Bot) -> None:
    async with session_scope() as session:
        active = await users.all_active(session)
        targets = [(u.id, u.telegram_id, u.language) for u in active]

    logger.info("daily.run_start", users=len(targets))
    for user_id, telegram_id, lang in targets:
        try:
            await deliver_daily_for_user(bot, user_id, telegram_id, lang)
            # Be polite to Telegram's rate limits.
            await asyncio.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            logger.exception("daily.user_failed", user_id=user_id, error=str(exc))
    logger.info("daily.run_done")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone(settings.daily_delivery_timezone))
    scheduler.add_job(
        deliver_daily_all,
        trigger=CronTrigger(
            hour=settings.daily_delivery_hour,
            minute=settings.daily_delivery_minute,
            timezone=timezone(settings.daily_delivery_timezone),
        ),
        kwargs={"bot": bot},
        id="daily_delivery",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "scheduler.started",
        time=settings.daily_delivery_time,
        tz=settings.daily_delivery_timezone,
    )
    return scheduler
