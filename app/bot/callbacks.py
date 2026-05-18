"""Inline callback data factories (aiogram 3 CallbackData)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class AnswerCB(CallbackData, prefix="a"):
    """User selected an option in a quiz question."""

    trainer: str  # e.g. "mcs65.flag_to_letter"
    entry: str  # entry_code, e.g. "A"
    chosen: str  # the code the user picked
    correct: str  # the correct code (kept here so the handler is stateless)
    mode: str = "i"  # i = interactive (edit in place), d = daily delivery


class NextCB(CallbackData, prefix="n"):
    """User pressed «Next question» inside a topic session."""

    topic: str  # topic code; trainer is picked freshly each tap


class TopicCB(CallbackData, prefix="t"):
    """User started a training topic from the menu."""

    subject: str
    topic: str


class NavCB(CallbackData, prefix="nv"):
    """Top-level navigation between menu screens.

    target values:
        main      — main menu (3 sections)
        training  — list of training topics
        reference — list of reference topics
        stats     — statistics screen
    """

    target: str


class RefCB(CallbackData, prefix="r"):
    """Open one reference (theory) page."""

    section: str


class RefDetailCB(CallbackData, prefix="rd"):
    """Open the detail page for a single entry inside a reference section.

    `code` is the canonical entry code — 'A'..'Z' for letters, 'N0'..'N9' for
    numeral pennants, 'S1'..'S3' for substitutes, 'AP' for the answering pennant.
    The handler determines what to render based on the prefix.
    """

    code: str
