"""Renders questions to Telegram messages and handles answer recording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import AnswerCB, NextCB
from app.i18n import t
from app.logger import get_logger
from app.repositories import history
from app.training.base import Question
from app.training.registry import registry

logger = get_logger(__name__)


@dataclass(frozen=True)
class SentQuestion:
    question: Question
    message_id: int
    chat_id: int


def build_answer_keyboard(question: Question) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for opt in question.options:
        cb = AnswerCB(
            trainer=question.trainer_key,
            entry=question.entry_code,
            chosen=opt.code,
            correct=question.correct_code,
        )
        rows.append([InlineKeyboardButton(text=opt.label, callback_data=cb.pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_next_keyboard(topic: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("common.next_question", lang),
                    callback_data=NextCB(topic=topic).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("menu.back_to_menu", lang),
                    callback_data="menu:open",
                )
            ],
        ]
    )


async def send_question(
    bot: Bot,
    chat_id: int,
    question: Question,
    *,
    prefix: str | None = None,
) -> SentQuestion:
    """Send a question with multiple-choice keyboard. `prefix` adds context (e.g. review marker)."""
    keyboard = build_answer_keyboard(question)
    caption_parts = [p for p in (prefix, question.prompt_text) if p]
    text = "\n\n".join(caption_parts)
    photo = None
    if question.prompt_image_path is not None:
        photo = FSInputFile(str(question.prompt_image_path))
    elif question.prompt_image_bytes is not None:
        photo = BufferedInputFile(question.prompt_image_bytes, filename="quiz.png")
    if photo is not None:
        msg = await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, reply_markup=keyboard)
    else:
        msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
    return SentQuestion(question=question, message_id=msg.message_id, chat_id=chat_id)


async def record_and_format_result(
    session: AsyncSession,
    *,
    user_id: int,
    trainer_key: str,
    entry_code: str,
    chosen: str,
    correct: str,
    lang: str,
) -> tuple[bool, str, Path | None]:
    """Record the answer, build the result message, and optionally an answer image.

    The image (when set by the trainer) is shown beside the result text — it's
    used by «visual grid» trainers so the user always sees which flag was the
    correct one regardless of whether they picked it.
    """
    is_correct = chosen == correct
    trainer = registry.get_trainer(trainer_key)
    await history.record_answer(
        session,
        user_id=user_id,
        subject=trainer.subject,
        topic=trainer.topic,
        trainer_key=trainer_key,
        entry_code=entry_code,
        is_correct=is_correct,
    )

    if is_correct:
        verdict = t("quiz.correct", lang)
    else:
        verdict = t("quiz.incorrect", lang, answer=correct)

    question = trainer.build_question(entry_code, lang)
    explanation = question.explanation or ""
    body = f"{verdict}\n\n{explanation}".strip()
    return is_correct, body, trainer.build_answer_image(entry_code)


def build_question_from_pick(trainer_key: str, entry_code: str, lang: str) -> Question:
    return registry.get_trainer(trainer_key).build_question(entry_code, lang)
