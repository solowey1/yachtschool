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

    Two-tier: `target` picks the menu section, `subject` (optional) picks
    the maritime subject inside it.

    target values:
        main      — main menu (4 sections)
        training  — without `subject`: subject picker; with `subject`:
                    open that subject's training menu (or, for single-topic
                    subjects, launch the trainer directly)
        reference — same scheme as training
        stats     — statistics screen
        settings  — settings screen
    """

    target: str
    subject: str | None = None


class RefCB(CallbackData, prefix="r"):
    """Open a reference (theory) page.

    `subject` is the maritime subject (e.g. "mcs65", "colregs");
    `section` is a per-subject identifier (e.g. "flags" for MCS, "part_a"
    for COLREGs); `item` drills further within a section (e.g. a specific
    COLREGs rule under a part — left None when not applicable).
    """

    subject: str
    section: str
    item: str | None = None


class RefDetailCB(CallbackData, prefix="rd"):
    """Open the detail page for a single entry inside a reference section.

    `code` is the canonical entry code — 'A'..'Z' for letters, 'N0'..'N9' for
    numeral pennants, 'S1'..'S3' for substitutes, 'AP' for the answering pennant.
    The handler determines what to render based on the prefix.
    """

    code: str


class DonateCB(CallbackData, prefix="dn"):
    """User picked a Stars amount to donate."""

    amount: int


class ColregsCB(CallbackData, prefix="cl"):
    """МППСС training submenu and trainer settings.

    actions:
      menu          — show submenu (start / settings / back)
      start         — launch a scenario respecting current user prefs
      settings      — open the per-trainer settings page
      toggle_night  — flip night-mode flag, rerender settings page
      toggle_type   — toggle one vessel type on/off; `value` carries the
                      type code (sail / motor / fishing / nuc / ram)
    """

    action: str
    value: str | None = None


class SettingsCB(CallbackData, prefix="st"):
    """Settings navigation and mutation.

    action: 'view'  — open a settings page (field selects which one: lang/count/time)
            'set'   — apply value to field
            'reset' — clear user's override, fall back to env default

    Time values are encoded as 'HHMM' (no colon) — colon is the CallbackData
    separator in aiogram and would corrupt parsing.

    `field` and `value` are nullable: aiogram decodes empty string segments
    as None on unpack, so declaring them as `str` would trip pydantic with
    ValidationError → handler never runs → user sees eternal loading.
    """

    action: str
    field: str | None = None
    value: str | None = None
