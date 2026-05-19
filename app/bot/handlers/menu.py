from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import NavCB, NextCB, RefCB, RefDetailCB, TopicCB
from app.bot.handlers.reference import build_detail, build_reference_text, detail_section_for
from app.bot.handlers.reference_colregs import (
    CHAPTER_RULES,
    about_text as colregs_about,
    chapter_intro as colregs_chapter_intro,
    rule_text as colregs_rule_text,
)
from app.bot.handlers.stats import build_stats_text
from app.bot.keyboards import (
    main_menu,
    reference_back_to_part,
    reference_colregs_menu,
    reference_colregs_part,
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
from app.services.question_picker import pick_for_topic
from app.services.quiz_engine import build_question_from_pick, edit_to_question, send_question
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
async def start_colregs_training(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    """Single-topic subject: skip topic picker, launch the trainer directly."""
    pick = await pick_for_topic(session, user.id, "colregs", "encounter")
    if pick is None or cq.message is None:
        await _swap_text(cq, t("quiz.no_more_questions", lang), main_menu(lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    topic = registry.get_topic("colregs", "encounter")
    prefix = t(topic.intro_i18n_key, lang)

    try:
        await cq.message.delete()
    except TelegramBadRequest:
        pass
    await send_question(cq.bot, cq.from_user.id, question, prefix=prefix)
    await cq.answer()


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


@router.callback_query(RefCB.filter((F.subject == "colregs") & (F.item.is_(None))))
async def open_reference_colregs_section(
    cq: CallbackQuery, callback_data: RefCB, lang: str
) -> None:
    """Chapter intro page. «about» has no rules — just text + back; the rest
    show the rule-number buttons under the intro.
    """
    section = callback_data.section
    if section == "about":
        text = colregs_about(lang)
        keyboard = reference_back_to_part(lang, "about")  # actually returns to colregs menu — fix below
        # Actually, "about" doesn't drill further. Back goes to colregs menu.
        from app.bot.callbacks import NavCB as _NavCB
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("menu.back_to_section", lang),
                        callback_data=_NavCB(target="reference", subject="colregs").pack(),
                    )
                ]
            ]
        )
    elif section in CHAPTER_RULES:
        text = colregs_chapter_intro(section, lang)
        keyboard = reference_colregs_part(lang, section)
    else:
        text = t("common.error", lang)
        keyboard = reference_colregs_menu(lang)
    await _swap_text(cq, text, keyboard)
    await cq.answer()


@router.callback_query(RefCB.filter((F.subject == "colregs") & (F.item.is_not(None))))
async def open_reference_colregs_rule(
    cq: CallbackQuery, callback_data: RefCB, lang: str
) -> None:
    """Single COLREGs rule page."""
    rule = callback_data.item or ""
    text = colregs_rule_text(rule, lang)
    keyboard = reference_back_to_part(lang, callback_data.section)
    await _swap_text(cq, text, keyboard)
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

    pick = await pick_for_topic(session, user.id, topic_obj.subject, topic_obj.code)
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

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    await edit_to_question(cq.bot, cq.message.chat.id, cq.message.message_id, question)
    await cq.answer()
