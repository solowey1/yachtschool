from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import ColregsCB, NavCB, NextCB, RefCB, RefDetailCB, TopicCB
from app.bot.handlers.reference import build_detail, build_reference_text, detail_section_for
from app.bot.handlers.reference_colregs import (
    CHAPTER_RULES,
)
from app.bot.handlers.reference_colregs import (
    chapter_full_text as colregs_chapter_full_text,
)
from app.bot.handlers.stats import build_stats_text
from app.bot.keyboards import (
    colregs_settings,
    colregs_submenu,
    main_menu,
    reference_colregs_chapter_back,
    reference_colregs_menu,
    reference_detail_back,
    reference_mcs65_menu,
    reference_section_keyboard,
    reference_subject_picker,
    stats_back,
    training_subject_picker,
    training_topics,
)
from app.db.models import User
from app.i18n import t
from app.services import user_settings
from app.services.question_picker import pick_for_topic
from app.services.quiz_engine import build_question_from_pick, edit_to_question, send_question
from app.training.colregs.data import involved_types
from app.training.registry import registry

router = Router(name="menu")


async def _swap_text(cq: CallbackQuery, text: str, keyboard) -> None:
    """Edit the current text message, sending a new one only if edit isn't possible.

    Photo→text transitions can't be done as an edit — Telegram won't change
    the message type — so we delete and resend.
    """
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


TELEGRAM_TEXT_LIMIT = 4096


def _split_html(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    """Split a long HTML string into ≤limit-char chunks on paragraph, then
    line, boundaries. Never splits mid-tag for our content because every tag
    in the reference (<b>/<i>/<code>) is opened and closed within one line.
    """
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        candidate = para if not buf else f"{buf}\n\n{para}"
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        # `para` alone may still exceed the limit — fall back to line splitting.
        if len(para) <= limit:
            buf = para
            continue
        line_buf = ""
        for line in para.split("\n"):
            cand2 = line if not line_buf else f"{line_buf}\n{line}"
            if len(cand2) <= limit:
                line_buf = cand2
            else:
                if line_buf:
                    chunks.append(line_buf)
                # Single line longer than the limit — hard-slice it.
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                line_buf = line
        buf = line_buf
    if buf:
        chunks.append(buf)
    return chunks


async def _swap_long(cq: CallbackQuery, text: str, keyboard) -> None:
    """Render a long reference article as one or more messages.

    The first chunk replaces the current (menu) message; extra chunks are
    sent as follow-ups. The back-button keyboard rides on the last chunk.
    """
    if cq.message is None:
        return
    chunks = _split_html(text)
    last = len(chunks) - 1

    # First chunk: edit in place when the current message is text, else resend.
    first_kb = keyboard if last == 0 else None
    if cq.message.photo:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
        await cq.message.answer(chunks[0], reply_markup=first_kb)
    else:
        try:
            await cq.message.edit_text(chunks[0], reply_markup=first_kb)
        except TelegramBadRequest:
            await cq.message.answer(chunks[0], reply_markup=first_kb)

    for i in range(1, len(chunks)):
        await cq.message.answer(chunks[i], reply_markup=keyboard if i == last else None)


# ── Top-level navigation ─────────────────────────────────────────────────────

@router.callback_query(NavCB.filter((F.target == "main") & (F.subject.is_(None))))
async def open_main(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.main_title", lang), main_menu(lang))
    await cq.answer()


@router.callback_query(NavCB.filter((F.target == "stats") & (F.subject.is_(None))))
async def open_stats(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    text = await build_stats_text(session, user, lang)
    await _swap_text(cq, text, stats_back(lang))
    await cq.answer()


# ── Training: two-tier (subject → topic) ─────────────────────────────────────

@router.callback_query(NavCB.filter((F.target == "training") & (F.subject.is_(None))))
async def open_training_subjects(cq: CallbackQuery, lang: str) -> None:
    """First click on «🎯 Обучение» — pick a maritime subject."""
    await _swap_text(
        cq, t("menu.training_subject_title", lang), training_subject_picker(lang)
    )
    await cq.answer()


@router.callback_query(
    NavCB.filter((F.target == "training") & (F.subject == "mcs65"))
)
async def open_training_mcs65(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.training_mcs65_title", lang), training_topics(lang, "mcs65"))
    await cq.answer()


@router.callback_query(
    NavCB.filter((F.target == "training") & (F.subject == "colregs"))
)
async def open_colregs_submenu(cq: CallbackQuery, lang: str) -> None:
    """МППСС-72 picked from training subject list → show submenu (start /
    settings / back). Settings live next to the launch button so toggling
    night-mode or vessel types takes a single tap from the trainer screen.
    """
    await _swap_text(cq, t("colregs.menu_title", lang), colregs_submenu(lang))
    await cq.answer()


def _colregs_filter_fn(enabled: set[str]):
    """Build a filter_fn for pick_for_topic that drops scenarios whose
    encounter type uses a vessel kind the user has disabled.
    """

    def fn(trainer_key: str, entry_code: str) -> bool:
        if not entry_code.startswith("colregs_"):
            return True
        types_in_scene = {vt.value for vt in involved_types(entry_code)}
        return types_in_scene.issubset(enabled)

    return fn


async def _launch_colregs_scenario(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    enabled = user_settings.colregs_enabled_types(user)
    night = user_settings.colregs_night_mode(user)
    pick = await pick_for_topic(
        session, user.id, "colregs", "encounter", filter_fn=_colregs_filter_fn(enabled)
    )
    if pick is None or cq.message is None:
        await _swap_text(cq, t("quiz.no_more_questions", lang), main_menu(lang))
        await cq.answer()
        return

    question = build_question_from_pick(
        pick.trainer_key, pick.entry_code, lang, night_mode=night
    )
    topic = registry.get_topic("colregs", "encounter")
    prefix = t(topic.intro_i18n_key, lang)

    try:
        await cq.message.delete()
    except TelegramBadRequest:
        pass
    await send_question(cq.bot, cq.from_user.id, question, prefix=prefix)
    await cq.answer()


@router.callback_query(ColregsCB.filter(F.action == "menu"))
async def back_to_colregs_submenu(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("colregs.menu_title", lang), colregs_submenu(lang))
    await cq.answer()


@router.callback_query(ColregsCB.filter(F.action == "start"))
async def colregs_start_trainer(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    await _launch_colregs_scenario(cq, session, user, lang)


def _colregs_settings_text(user: User, lang: str) -> str:
    enabled = user_settings.colregs_enabled_types(user)
    night = user_settings.colregs_night_mode(user)
    type_lines = "\n".join(
        f"  {'✅' if code in enabled else '⬜'} {t(f'colregs.vessel_type.{code}', lang)}"
        for code in user_settings.colregs_all_types()
    )
    return t(
        "colregs.settings_text",
        lang,
        mode=t("colregs.mode_night" if night else "colregs.mode_day", lang),
        types=type_lines,
    )


@router.callback_query(ColregsCB.filter(F.action == "settings"))
async def colregs_open_settings(cq: CallbackQuery, user: User, lang: str) -> None:
    await _swap_text(
        cq,
        _colregs_settings_text(user, lang),
        colregs_settings(
            lang,
            night_mode=user_settings.colregs_night_mode(user),
            enabled_types=user_settings.colregs_enabled_types(user),
        ),
    )
    await cq.answer()


@router.callback_query(ColregsCB.filter(F.action == "toggle_night"))
async def colregs_toggle_night(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    user_settings.colregs_set_night_mode(user, not user_settings.colregs_night_mode(user))
    await session.flush()
    await _swap_text(
        cq,
        _colregs_settings_text(user, lang),
        colregs_settings(
            lang,
            night_mode=user_settings.colregs_night_mode(user),
            enabled_types=user_settings.colregs_enabled_types(user),
        ),
    )
    await cq.answer(t("settings.updated", lang))


@router.callback_query(ColregsCB.filter(F.action == "toggle_type"))
async def colregs_toggle_type(
    cq: CallbackQuery,
    callback_data: ColregsCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    if callback_data.value:
        user_settings.colregs_toggle_type(user, callback_data.value)
        await session.flush()
    await _swap_text(
        cq,
        _colregs_settings_text(user, lang),
        colregs_settings(
            lang,
            night_mode=user_settings.colregs_night_mode(user),
            enabled_types=user_settings.colregs_enabled_types(user),
        ),
    )
    await cq.answer(t("settings.updated", lang))


# ── Reference: two-tier (subject → section → item) ───────────────────────────

@router.callback_query(NavCB.filter((F.target == "reference") & (F.subject.is_(None))))
async def open_reference_subjects(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(
        cq, t("menu.reference_subject_title", lang), reference_subject_picker(lang)
    )
    await cq.answer()


@router.callback_query(
    NavCB.filter((F.target == "reference") & (F.subject == "mcs65"))
)
async def open_reference_mcs65(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.reference_mcs65_title", lang), reference_mcs65_menu(lang))
    await cq.answer()


@router.callback_query(
    NavCB.filter((F.target == "reference") & (F.subject == "colregs"))
)
async def open_reference_colregs(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.reference_colregs_title", lang), reference_colregs_menu(lang))
    await cq.answer()


@router.callback_query(RefCB.filter(F.subject == "mcs65"))
async def open_reference_mcs65_section(
    cq: CallbackQuery, callback_data: RefCB, lang: str
) -> None:
    text = build_reference_text(callback_data.section, lang)
    keyboard = reference_section_keyboard(callback_data.section, lang)
    await _swap_text(cq, text, keyboard)
    await cq.answer()


@router.callback_query(RefCB.filter(F.subject == "colregs"))
async def open_reference_colregs_section(
    cq: CallbackQuery, callback_data: RefCB, lang: str
) -> None:
    """Full chapter as a long-form article — «about» or a Part with all its
    rules inline. No per-rule pagination: the whole chapter is one long
    message (auto-split when it exceeds Telegram's 4096-char limit).
    """
    section = callback_data.section
    if section != "about" and section not in CHAPTER_RULES:
        await _swap_text(cq, t("common.error", lang), reference_colregs_menu(lang))
        await cq.answer()
        return
    text = colregs_chapter_full_text(section, lang)
    await _swap_long(cq, text, reference_colregs_chapter_back(lang))
    await cq.answer()


@router.callback_query(RefDetailCB.filter())
async def open_reference_detail(
    cq: CallbackQuery, callback_data: RefDetailCB, lang: str
) -> None:
    """МСС-65 drill-down (letter / numeral / substitute) — text → photo detail."""
    image_path, caption = build_detail(callback_data.code, lang)
    back_section = detail_section_for(callback_data.code)
    keyboard = reference_detail_back(back_section, lang)

    if cq.message is not None:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
    await cq.bot.send_photo(
        chat_id=cq.from_user.id,
        photo=FSInputFile(str(image_path)),
        caption=caption,
        reply_markup=keyboard,
    )
    await cq.answer()


# ── Topic launch (МСС-65) ────────────────────────────────────────────────────

@router.callback_query(TopicCB.filter())
async def start_topic(
    cq: CallbackQuery,
    callback_data: TopicCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    pick = await pick_for_topic(session, user.id, callback_data.subject, callback_data.topic)
    if pick is None:
        await _swap_text(cq, t("quiz.no_more_questions", lang), main_menu(lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    topic = registry.get_topic(callback_data.subject, callback_data.topic)
    prefix = t(topic.intro_i18n_key, lang)

    if cq.message is not None:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
    await send_question(cq.bot, cq.from_user.id, question, prefix=prefix)
    await cq.answer()


@router.callback_query(NextCB.filter())
async def next_question(
    cq: CallbackQuery,
    callback_data: NextCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    topic_obj = next((tp for tp in registry.topics() if tp.code == callback_data.topic), None)
    if topic_obj is None:
        await cq.answer(t("common.error", lang), show_alert=True)
        return

    # COLREGs: respect the user's vessel-type filter and night-mode toggle.
    filter_fn = None
    opts: dict = {}
    if topic_obj.subject == "colregs":
        enabled = user_settings.colregs_enabled_types(user)
        filter_fn = _colregs_filter_fn(enabled)
        opts["night_mode"] = user_settings.colregs_night_mode(user)

    pick = await pick_for_topic(
        session, user.id, topic_obj.subject, topic_obj.code, filter_fn=filter_fn
    )
    if cq.message is None:
        await cq.answer()
        return
    if pick is None:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
        await cq.message.answer(t("quiz.no_more_questions", lang), reply_markup=main_menu(lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang, **opts)
    await edit_to_question(cq.bot, cq.message.chat.id, cq.message.message_id, question)
    await cq.answer()
