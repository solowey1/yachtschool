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
from app.training.registry import registry

router = Router(name="stats")


def _percent(correct: int, total: int) -> int:
    return round(correct * 100 / total) if total else 0


def _topic_label(subject: str, topic_code: str, lang: str) -> str:
    """Resolve the localised topic name via the registry so subjects that use
    namespaced i18n keys (e.g. «menu.topic.colregs_encounter») don't fall
    back to the raw code in the stats screen.
    """
    try:
        return t(registry.get_topic(subject, topic_code).title_i18n_key, lang)
    except KeyError:
        return topic_code


def _subject_header(subject: str, lang: str, total: int, correct: int, skipped: int) -> str:
    return t(
        "stats.subject_header",
        lang,
        subject=t(f"menu.subject.{subject}", lang),
        total=total,
        correct=correct,
        skipped=skipped,
        percent=_percent(correct, total),
    )


def _subject_block(subject: str, lang: str, topics: list[tuple[str, int, int, int]]) -> str:
    """One subject's stats block. Each tuple = (topic, total, correct, skipped)."""
    total = sum(n for _, n, _, _ in topics)
    correct = sum(c for _, _, c, _ in topics)
    skipped = sum(s for _, _, _, s in topics)
    head = _subject_header(subject, lang, total, correct, skipped)
    if not topics:
        return head
    rows = "\n".join(
        t(
            "stats.by_topic_row",
            lang,
            topic=_topic_label(subject, tcode, lang),
            correct=tcorrect,
            total=ttotal,
            percent=_percent(tcorrect, ttotal),
        )
        for tcode, ttotal, tcorrect, _tskipped in sorted(topics)
    )
    return f"{head}\n{rows}"


async def build_stats_text(session: AsyncSession, user: User, lang: str) -> str:
    rows = await history.subject_topic_stats(session, user.id)
    if not rows:
        return t("stats.empty", lang)

    grouped: dict[str, list[tuple[str, int, int, int]]] = defaultdict(list)
    for subject, topic, ttotal, tcorrect, tskipped in rows:
        grouped[subject].append((topic, ttotal, tcorrect, tskipped))

    blocks: list[str] = []
    for subject in SUBJECTS:
        if subject in grouped:
            blocks.append(_subject_block(subject, lang, grouped[subject]))
    for subject in grouped:
        if subject not in SUBJECTS:
            blocks.append(_subject_block(subject, lang, grouped[subject]))

    overall_total = sum(n for _, _, n, _, _ in rows)
    overall_correct = sum(c for _, _, _, c, _ in rows)
    overall_skipped = sum(s for _, _, _, _, s in rows)
    overall_wrong = overall_total - overall_correct - overall_skipped
    overall = t(
        "stats.overall",
        lang,
        total=overall_total,
        correct=overall_correct,
        wrong=overall_wrong,
        skipped=overall_skipped,
        percent=_percent(overall_correct, overall_total),
    )

    return t("stats.title", lang) + "\n\n" + overall + "\n\n" + "\n\n".join(blocks)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User, lang: str) -> None:
    text = await build_stats_text(session, user, lang)
    await message.answer(text, reply_markup=stats_back(lang))
