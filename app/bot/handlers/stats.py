from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.i18n import t
from app.repositories import history

router = Router(name="stats")


async def _build_stats_text(session: AsyncSession, user: User, lang: str) -> str:
    total, correct = await history.overall_stats(session, user.id)
    if total == 0:
        return t("stats.empty", lang)

    wrong_pairs = await history.latest_wrong_answers(session, user.id)
    percent = round(correct * 100 / total) if total else 0

    summary = t(
        "stats.summary",
        lang,
        total=total,
        correct=correct,
        percent=percent,
        wrong=len(wrong_pairs),
    )

    topic_rows = await history.topic_stats(session, user.id)
    if topic_rows:
        formatted = "\n".join(
            t(
                "stats.by_topic_row",
                lang,
                topic=t(f"menu.topic.{tcode}", lang),
                correct=tcorrect,
                total=ttotal,
                percent=round(tcorrect * 100 / ttotal) if ttotal else 0,
            )
            for tcode, ttotal, tcorrect in sorted(topic_rows)
        )
        summary += t("stats.by_topic", lang, rows=formatted)

    return f"{t('stats.title', lang)}\n\n{summary}"


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User, lang: str) -> None:
    text = await _build_stats_text(session, user, lang)
    await message.answer(text)


@router.callback_query(F.data == "stats:open")
async def cb_stats(cq: CallbackQuery, session: AsyncSession, user: User, lang: str) -> None:
    text = await _build_stats_text(session, user, lang)
    await cq.message.answer(text)
    await cq.answer()
