"""Inline callback data factories (aiogram 3 CallbackData)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class AnswerCB(CallbackData, prefix="a"):
    """User selected an option in a quiz question."""

    trainer: str  # e.g. "mcs65.flag_to_letter"
    entry: str  # entry_code, e.g. "A"
    chosen: str  # the code the user picked
    correct: str  # the correct code (kept here so the handler is stateless)


class NextCB(CallbackData, prefix="n"):
    """User pressed «Next question» inside a topic session."""

    topic: str  # topic code; trainer is picked freshly each tap


class TopicCB(CallbackData, prefix="t"):
    """User opened a topic from the main menu."""

    subject: str
    topic: str
