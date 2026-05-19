"""Renders questions to Telegram messages and handles answer recording.

All quiz messages are sent as photos so that question → result → next-question
transitions can be applied via `edit_message_media` without ever creating a
new chat message during a quiz session.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    daily_result_keyboard,
    quiz_answer_keyboard,
    quiz_next_keyboard,
)
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


def _question_media(question: Question, caption: str) -> InputMediaPhoto:
    if question.prompt_image_path is not None:
        photo = FSInputFile(str(question.prompt_image_path))
    elif question.prompt_image_bytes is not None:
        photo = BufferedInputFile(question.prompt_image_bytes, filename="quiz.png")
    else:
        raise ValueError(f"question {question.trainer_key}:{question.entry_code} has no image")
    return InputMediaPhoto(media=photo, caption=caption)


def _build_caption(question: Question, prefix: str | None) -> str:
    parts = [p for p in (prefix, question.prompt_text) if p]
    return "\n\n".join(parts)


async def send_question(
    bot: Bot,
    chat_id: int,
    question: Question,
    *,
    prefix: str | None = None,
    mode: str = "i",
) -> SentQuestion:
    """Send a brand-new question message. Used at quiz entry and for daily delivery."""
    caption = _build_caption(question, prefix)
    media = _question_media(question, caption)
    msg = await bot.send_photo(
        chat_id=chat_id,
        photo=media.media,
        caption=caption,
        reply_markup=quiz_answer_keyboard(question, mode=mode),
    )
    return SentQuestion(question=question, message_id=msg.message_id, chat_id=chat_id)


async def edit_to_question(
    bot: Bot,
    chat_id: int,
    message_id: int,
    question: Question,
    *,
    prefix: str | None = None,
    mode: str = "i",
) -> None:
    """Replace an existing photo message with a new question (same chat thread)."""
    caption = _build_caption(question, prefix)
    media = _question_media(question, caption)
    await bot.edit_message_media(
        chat_id=chat_id,
        message_id=message_id,
        media=media,
        reply_markup=quiz_answer_keyboard(question, mode=mode),
    )


async def edit_to_result(
    bot: Bot,
    chat_id: int,
    message_id: int,
    *,
    body: str,
    answer_image_path: Path | None,
    keyboard: InlineKeyboardMarkup,
) -> None:
    """Transition a quiz message from question into result.

    When the trainer supplies an answer image, we `edit_message_media` so the
    user sees the correct flag full-size with the verdict as caption. Otherwise
    we keep the current photo and only update the caption.
    """
    if answer_image_path is not None:
        media = InputMediaPhoto(media=FSInputFile(str(answer_image_path)), caption=body)
        await bot.edit_message_media(
            chat_id=chat_id, message_id=message_id, media=media, reply_markup=keyboard
        )
    else:
        await bot.edit_message_caption(
            chat_id=chat_id, message_id=message_id, caption=body, reply_markup=keyboard
        )


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

    question = trainer.build_question(entry_code, lang)
    correct_answer_for_verdict = question.correct_label or correct
    verdict = (
        t("quiz.correct", lang)
        if is_correct
        else t("quiz.incorrect", lang, answer=correct_answer_for_verdict)
    )
    explanation = question.explanation or ""
    body = f"{verdict}\n\n{explanation}".strip()
    return is_correct, body, trainer.build_answer_image(entry_code)


def build_question_from_pick(
    trainer_key: str, entry_code: str, lang: str, **opts
) -> Question:
    """Construct a question from a (trainer, entry) pick.

    `**opts` are trainer-specific extras (e.g. `night_mode=True` for the
    COLREGs trainer). Only opts the trainer's `build_question` actually
    accepts get forwarded — other trainers see a plain
    (entry_code, lang) call.
    """
    import inspect

    trainer = registry.get_trainer(trainer_key)
    params = inspect.signature(trainer.build_question).parameters
    has_var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
    accepted = opts if has_var_kw else {k: v for k, v in opts.items() if k in params}
    return trainer.build_question(entry_code, lang, **accepted)


def keyboard_after_answer(mode: str, topic: str, lang: str) -> InlineKeyboardMarkup:
    """Daily questions have no «Next» button — the next one is already in chat."""
    return daily_result_keyboard(lang) if mode == "d" else quiz_next_keyboard(topic, lang)
