from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import NavCB, NextCB, RefCB, TopicCB
from app.bot.keyboards import (
    main_menu,
    reference_back,
    reference_menu,
    stats_back,
    training_menu,
)
from app.bot.handlers.stats import build_stats_text
from app.bot.handlers.reference import build_reference_text
from app.db.models import User
from app.i18n import t
from app.services.question_picker import pick_for_topic
from app.services.quiz_engine import build_question_from_pick, edit_to_question, send_question
from app.training.registry import registry

router = Router(name="menu")


async def _swap_text(cq: CallbackQuery, text: str, keyboard) -> None:
    """Edit the current text message, sending a new one only if edit isn't possible.

    A text→text transition is always editable. Photo→text isn't — Telegram
    can't change the message type — so we delete and resend.
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
        # Nothing to edit (message too old) or content identical — send a fresh one.
        await cq.message.answer(text, reply_markup=keyboard)


@router.callback_query(NavCB.filter(F.target == "main"))
async def open_main(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.main_title", lang), main_menu(lang))
    await cq.answer()


@router.callback_query(NavCB.filter(F.target == "training"))
async def open_training(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.training_title", lang), training_menu(lang))
    await cq.answer()


@router.callback_query(NavCB.filter(F.target == "reference"))
async def open_reference(cq: CallbackQuery, lang: str) -> None:
    await _swap_text(cq, t("menu.reference_title", lang), reference_menu(lang))
    await cq.answer()


@router.callback_query(NavCB.filter(F.target == "stats"))
async def open_stats(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    text = await build_stats_text(session, user, lang)
    await _swap_text(cq, text, stats_back(lang))
    await cq.answer()


@router.callback_query(RefCB.filter())
async def open_reference_section(
    cq: CallbackQuery, callback_data: RefCB, lang: str
) -> None:
    text = build_reference_text(callback_data.section, lang)
    await _swap_text(cq, text, reference_back(lang))
    await cq.answer()


@router.callback_query(TopicCB.filter())
async def start_topic(
    cq: CallbackQuery,
    callback_data: TopicCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    """Enter a training topic — text menu becomes a photo quiz message."""
    pick = await pick_for_topic(session, user.id, callback_data.subject, callback_data.topic)
    if pick is None:
        await _swap_text(cq, t("quiz.no_more_questions", lang), main_menu(lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    topic = registry.get_topic(callback_data.subject, callback_data.topic)
    prefix = t(topic.intro_i18n_key, lang)

    # Menu was text, quiz is a photo — type change forces delete + send.
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
        # Out of unseen questions — drop back to text menu.
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
