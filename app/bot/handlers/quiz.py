from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import AnswerCB
from app.db.models import User
from app.services.quiz_engine import build_next_keyboard, record_and_format_result
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
    is_correct, body = await record_and_format_result(
        session,
        user_id=user.id,
        trainer_key=callback_data.trainer,
        entry_code=callback_data.entry,
        chosen=callback_data.chosen,
        correct=callback_data.correct,
        lang=lang,
    )

    # Remove the answer buttons on the original question so it can't be re-answered.
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass

    topic = registry.get_trainer(callback_data.trainer).topic
    await cq.message.answer(body, reply_markup=build_next_keyboard(topic, lang))
    await cq.answer("✅" if is_correct else "❌")
