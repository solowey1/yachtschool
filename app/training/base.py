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

    `prompt_text` is always present. Visual prompts are carried either as a
    cached file path (`prompt_image_path`) or as in-memory PNG bytes
    (`prompt_image_bytes`) — the latter is used for dynamically-composed
    images such as 4-flag answer grids where caching every permutation would
    blow up disk.
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
    prompt_image_bytes: bytes | None = None
    #: Human-readable form of the correct answer, used in the result verdict
    #: («Правильный ответ: <correct_label>»). Falls back to `correct_code` when None.
    correct_label: str | None = None


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

    def build_answer_image(self, entry_code: str) -> Path | None:
        """Optional image of the correct answer, attached to the result message.

        Used by «visual grid» trainers — where the prompt shows a numbered grid
        of candidate flags and the result message reveals which one was right.
        Default `None` means «no extra image after answering».
        """
        return None
