from __future__ import annotations

from collections import defaultdict

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import StatsCB, StatsNavCB
from app.bot.keyboards import (
    DETAILED_STATS_STARS,
    SUBJECTS,
    stats_menu,
    stats_navigator,
    stats_paywall,
    stats_subject_back,
)
from app.db.models import User
from app.i18n import t
from app.logger import get_logger
from app.repositories import history
from app.services import stats_charts
from app.training.registry import registry

router = Router(name="stats")
logger = get_logger(__name__)

WEEKS_ON_CHART = 4
DETAILED_STATS_PAYLOAD = "detailed_stats"


def _percent(correct: int, total: int) -> int:
    return round(correct * 100 / total) if total else 0


def _topic_label(subject: str, topic_code: str, lang: str) -> str:
    try:
        return t(registry.get_topic(subject, topic_code).title_i18n_key, lang)
    except KeyError:
        return topic_code


async def _weekly_chart(session: AsyncSession, user_id: int, subject: str | None) -> str:
    lines = []
    for p in stats_charts.last_weeks(WEEKS_ON_CHART):
        total, correct, _ = await history.accuracy_in_range(
            session, user_id, p.start, p.end, subject
        )
        lines.append(stats_charts.chart_row(p.label, correct, total))
    return "\n".join(lines)


async def _swap(cq: CallbackQuery, text: str, keyboard) -> None:
    if cq.message is None:
        return
    if cq.message.photo:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
        await cq.message.answer(text, reply_markup=keyboard)
        return
    try:
        await cq.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await cq.message.answer(text, reply_markup=keyboard)


# ── Overall stats screen ─────────────────────────────────────────────────────

async def build_stats_text(session: AsyncSession, user: User, lang: str) -> str:
    total, correct = await history.overall_stats(session, user.id)
    if total == 0:
        return t("stats.empty", lang)
    chart = await _weekly_chart(session, user.id, None)
    return (
        t("stats.title", lang)
        + "\n\n"
        + t("stats.overall_short", lang, correct=correct, total=total, percent=_percent(correct, total))
        + "\n\n"
        + t("stats.weeks_header", lang)
        + "\n"
        + chart
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User, lang: str) -> None:
    text = await build_stats_text(session, user, lang)
    await message.answer(text, reply_markup=stats_menu(lang))


# ── Per-subject weekly chart ─────────────────────────────────────────────────

@router.callback_query(StatsCB.filter(F.action == "subject"))
async def stats_subject(
    cq: CallbackQuery, callback_data: StatsCB, session: AsyncSession, user: User, lang: str
) -> None:
    subject = callback_data.value or ""
    chart = await _weekly_chart(session, user.id, subject)

    # all-time per-topic breakdown + subject totals derived from it
    rows = [r for r in await history.subject_topic_stats(session, user.id) if r[0] == subject]
    total = sum(ttotal for _s, _tc, ttotal, _cc, _sk in rows)
    correct = sum(cc for _s, _tc, _tt, cc, _sk in rows)
    topic_lines = [
        t(
            "stats.by_topic_row",
            lang,
            topic=_topic_label(subject, tcode, lang),
            correct=tcorrect,
            total=ttotal,
            percent=_percent(tcorrect, ttotal),
        )
        for _s, tcode, ttotal, tcorrect, _sk in sorted(rows)
    ]
    body = t(
        "stats.subject_title",
        lang,
        subject=t(f"menu.subject.{subject}", lang),
        correct=correct,
        total=total,
        percent=_percent(correct, total),
    )
    text = body + "\n\n" + t("stats.weeks_header", lang) + "\n" + chart
    if topic_lines:
        text += "\n\n" + t("stats.by_topic_header", lang) + "\n" + "\n".join(topic_lines)
    await _swap(cq, text, stats_subject_back(lang))
    await cq.answer()


# ── Detailed stats: paywall / navigator ──────────────────────────────────────

@router.callback_query(StatsCB.filter(F.action == "detailed"))
async def stats_detailed(cq: CallbackQuery, user: User, lang: str) -> None:
    if user.detailed_stats_unlocked:
        await _render_navigator(cq, user, lang, unit="day", offset=0)
    else:
        await _swap(cq, t("stats.paywall", lang, stars=DETAILED_STATS_STARS), stats_paywall(lang))
    await cq.answer()


@router.callback_query(StatsCB.filter(F.action == "buy"))
async def stats_buy(cq: CallbackQuery, user: User, lang: str) -> None:
    if user.detailed_stats_unlocked:
        await _render_navigator(cq, user, lang, unit="day", offset=0)
        await cq.answer()
        return
    try:
        await cq.bot.send_invoice(
            chat_id=cq.from_user.id,
            title=t("stats.invoice_title", lang),
            description=t("stats.invoice_description", lang),
            payload=DETAILED_STATS_PAYLOAD,
            currency="XTR",
            prices=[LabeledPrice(label=t("stats.invoice_label", lang), amount=DETAILED_STATS_STARS)],
            provider_token="",
        )
        await cq.answer()
    except Exception as exc:  # noqa: BLE001
        logger.exception("stats.invoice_failed", error=str(exc))
        await cq.answer(t("common.error", lang), show_alert=True)


@router.callback_query(StatsNavCB.filter())
async def stats_navigate(
    cq: CallbackQuery, callback_data: StatsNavCB, user: User, lang: str
) -> None:
    if not user.detailed_stats_unlocked:
        await _swap(cq, t("stats.paywall", lang, stars=DETAILED_STATS_STARS), stats_paywall(lang))
        await cq.answer()
        return
    offset = min(0, int(callback_data.offset))  # never into the future
    await _render_navigator(cq, user, lang, unit=callback_data.unit, offset=offset)
    await cq.answer()


async def _render_navigator(
    cq: CallbackQuery, user: User, lang: str, *, unit: str, offset: int
) -> None:
    from app.db.session import session_scope

    period = stats_charts.period_for(unit, offset)
    async with session_scope() as session:
        total, correct, _ = await history.accuracy_in_range(
            session, user.id, period.start, period.end
        )
        rows = await history.subject_topic_stats_in_range(
            session, user.id, period.start, period.end
        )

    per_subject: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    for subject, _topic, ttotal, tcorrect, _sk in rows:
        ct, tt = per_subject[subject]
        per_subject[subject] = (ct + tcorrect, tt + ttotal)

    lines = [
        t("stats.detailed_title", lang),
        "",
        t(f"stats.unit_name_{unit}", lang) + ": <b>" + period.label + "</b>",
        "",
        stats_charts.chart_row(t("stats.row_overall", lang), correct, total),
    ]
    for subject in SUBJECTS:
        sc, st_ = per_subject.get(subject, (0, 0))
        lines.append(
            stats_charts.chart_row(t(f"menu.subject.{subject}", lang), sc, st_)
        )
    await _swap(cq, "\n".join(lines), stats_navigator(lang, unit, offset))
