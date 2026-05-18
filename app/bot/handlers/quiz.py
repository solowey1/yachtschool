from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import AnswerCB
from app.db.models import User
from app.services.quiz_engine import (
    edit_to_result,
    keyboard_after_answer,
    record_and_format_result,
)
from app.training.registry import registry

router = Router(name="quiz")


@router.callback_query(AnswerCB.filter())
async def on_answer(
    cq: CallbackQuery,
    callback_data: AnswerCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    is_correct, body, answer_image = await record_and_format_result(
        session,
        user_id=user.id,
        trainer_key=callback_data.trainer,
        entry_code=callback_data.entry,
        chosen=callback_data.chosen,
        correct=callback_data.correct,
        lang=lang,
    )

    if cq.message is None:
        await cq.answer("✅" if is_correct else "❌")
        return

    topic = registry.get_trainer(callback_data.trainer).topic
    keyboard = keyboard_after_answer(callback_data.mode, topic, lang)
    try:
        await edit_to_result(
            cq.bot,
            cq.message.chat.id,
            cq.message.message_id,
            body=body,
            answer_image_path=answer_image,
            keyboard=keyboard,
        )
    except TelegramBadRequest:
        # Message too old to edit — fall back to a follow-up reply.
        await cq.message.answer(body, reply_markup=keyboard)
    await cq.answer("✅" if is_correct else "❌")
