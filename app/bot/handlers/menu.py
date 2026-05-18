from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import NextCB, TopicCB
from app.bot.keyboards import main_menu
from app.db.models import User
from app.i18n import t
from app.services.question_picker import pick_for_topic
from app.services.quiz_engine import build_question_from_pick, send_question
from app.training.registry import registry

router = Router(name="menu")


@router.callback_query(F.data == "menu:open")
async def open_menu(cq: CallbackQuery, lang: str) -> None:
    await cq.message.answer(t("menu.title", lang), reply_markup=main_menu(lang))
    await cq.answer()


@router.callback_query(TopicCB.filter())
async def start_topic(
    cq: CallbackQuery,
    callback_data: TopicCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    topic = registry.get_topic(callback_data.subject, callback_data.topic)
    await cq.message.answer(t(topic.intro_i18n_key, lang))

    pick = await pick_for_topic(session, user.id, callback_data.subject, callback_data.topic)
    if pick is None:
        await cq.message.answer(t("quiz.no_more_questions", lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    await send_question(cq.bot, cq.message.chat.id, question)
    await cq.answer()


@router.callback_query(NextCB.filter())
async def next_question(
    cq: CallbackQuery,
    callback_data: NextCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    # Topic codes in this app are unique across subjects so far; in the multi-subject
    # future we'd encode subject in NextCB too.
    topic_obj = next((tp for tp in registry.topics() if tp.code == callback_data.topic), None)
    if topic_obj is None:
        await cq.answer(t("common.error", lang), show_alert=True)
        return

    pick = await pick_for_topic(session, user.id, topic_obj.subject, topic_obj.code)
    if pick is None:
        await cq.message.answer(t("quiz.no_more_questions", lang))
        await cq.answer()
        return

    question = build_question_from_pick(pick.trainer_key, pick.entry_code, lang)
    await send_question(cq.bot, cq.message.chat.id, question)
    await cq.answer()
