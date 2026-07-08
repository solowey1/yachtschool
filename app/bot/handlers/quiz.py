from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import AnswerCB
from app.db.models import User
from app.services.quiz_engine import (
    edit_to_result,
    keyboard_after_answer,
    record_and_format_result,
)
from app.services.scheduler import release_next_after_answer
from app.training.registry import registry

router = Router(name="quiz")

_TOAST = {"correct": "✅", "skipped": "⏭", "wrong": "❌"}


@router.callback_query(AnswerCB.filter())
async def on_answer(
    cq: CallbackQuery,
    callback_data: AnswerCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    outcome, body, answer_image = await record_and_format_result(
        session,
        user_id=user.id,
        trainer_key=callback_data.trainer,
        entry_code=callback_data.entry,
        chosen=callback_data.chosen,
        correct=callback_data.correct,
        lang=lang,
    )

    if cq.message is None:
        await cq.answer(_TOAST.get(outcome, ""))
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
        await cq.message.answer(body, reply_markup=keyboard)
    await cq.answer(_TOAST.get(outcome, ""))

    # Daily-mode answer → release the next queued question (if any). For
    # interactive answers this is a no-op (no queue entry matches).
    if callback_data.mode == "d":
        try:
            await release_next_after_answer(
                cq.bot,
                user.id,
                cq.from_user.id,
                callback_data.trainer,
                callback_data.entry,
            )
        except Exception:  # noqa: BLE001
            # Logged by middleware error handler; don't break the response.
            pass
