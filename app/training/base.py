"""Trainer framework — the extensibility seam for new maritime subjects.

A `Subject` (e.g. МСС-65, COLREGs in the future) groups `Topic`s that the user
sees in the main menu. Each topic is realised by one or more `Trainer`s — small
classes that know how to render a question from an `entry_code` belonging to
that subject's domain.

Adding a new subject means: creating a data module, registering trainers via
`registry.register(...)`, and adding i18n strings. No bot code needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Option:
    """Single choice rendered as an inline-keyboard button."""

    code: str  # the entry_code or other identifier the user is picking
    label: str  # user-visible button text


@dataclass(frozen=True)
class Question:
    """A renderable, answerable question.

    `prompt_text` is always present. `prompt_image_path` is set when the prompt
    is visual (a flag, a chart, etc.) — in that case `prompt_text` becomes the
    photo caption.
    """

    trainer_key: str
    subject: str
    topic: str
    entry_code: str
    prompt_text: str
    prompt_image_path: Path | None
    options: list[Option]
    correct_code: str
    explanation: str | None = None


class Trainer(ABC):
    """Abstract trainer — produces questions for one (subject, topic, mode)."""

    #: Globally unique key. Format: "<subject>.<mode>" — keep stable, it ends up in the DB.
    key: str
    #: Subject code (e.g. "mcs65").
    subject: str
    #: Topic code (e.g. "flags"). Topics are the items in the user's main menu.
    topic: str

    @abstractmethod
    def all_entry_codes(self) -> list[str]:
        """All entry codes this trainer can quiz on."""

    @abstractmethod
    def build_question(self, entry_code: str, lang: str) -> Question:
        """Build a localised multiple-choice question for `entry_code`."""
