from __future__ import annotations

from collections import defaultdict

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import SUBJECTS, stats_back
from app.db.models import User
from app.i18n import t
from app.repositories import history

router = Router(name="stats")


def _percent(correct: int, total: int) -> int:
    return round(correct * 100 / total) if total else 0


def _subject_block(subject: str, lang: str, topics: list[tuple[str, int, int]]) -> str:
    """One subject's stats block — header + per-topic lines."""
    total = sum(n for _, n, _ in topics)
    correct = sum(c for _, _, c in topics)
    head = _subject_header(subject, lang, total, correct)
    if not topics:
        return head
    rows = "\n".join(
        t(
            "stats.by_topic_row",
            lang,
            topic=t(f"menu.topic.{tcode}", lang),
            correct=tcorrect,
            total=ttotal,
            percent=_percent(tcorrect, ttotal),
        )
        for tcode, ttotal, tcorrect in sorted(topics)
    )
    return f"{head}\n{rows}"


def _subject_header(subject: str, lang: str, total: int, correct: int) -> str:
    return t(
        "stats.subject_header",
        lang,
        subject=t(f"menu.subject.{subject}", lang),
        total=total,
        correct=correct,
        percent=_percent(correct, total),
    )


async def build_stats_text(session: AsyncSession, user: User, lang: str) -> str:
    rows = await history.subject_topic_stats(session, user.id)
    if not rows:
        return t("stats.empty", lang)

    # Group by subject, preserving the canonical SUBJECTS ordering for display.
    grouped: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for subject, topic, ttotal, tcorrect in rows:
        grouped[subject].append((topic, ttotal, tcorrect))

    blocks: list[str] = []
    for subject in SUBJECTS:
        if subject in grouped:
            blocks.append(_subject_block(subject, lang, grouped[subject]))
    # Any unknown subjects (e.g. new subject added before SUBJECTS update) — append last
    for subject in grouped:
        if subject not in SUBJECTS:
            blocks.append(_subject_block(subject, lang, grouped[subject]))

    overall_total = sum(n for _, _, n, _ in rows)
    overall_correct = sum(c for _, _, _, c in rows)
    wrong_pairs = await history.latest_wrong_answers(session, user.id)
    overall = t(
        "stats.overall",
        lang,
        total=overall_total,
        correct=overall_correct,
        percent=_percent(overall_correct, overall_total),
        wrong=len(wrong_pairs),
    )

    return t("stats.title", lang) + "\n\n" + overall + "\n\n" + "\n\n".join(blocks)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User, lang: str) -> None:
    text = await build_stats_text(session, user, lang)
    await message.answer(text, reply_markup=stats_back(lang))
