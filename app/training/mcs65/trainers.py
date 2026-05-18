"""Concrete МСС-65 trainers and topic registration."""

from __future__ import annotations

import random
from collections.abc import Callable

from app.i18n import t
from app.training.base import Option, Question, Trainer
from app.training.mcs65 import data, flag_renderer
from app.training.mcs65.data import SUBJECT_CODE
from app.training.registry import registry

OPTIONS_PER_QUESTION = 4


def _sample_distractors(correct: str, pool: list[str], n: int) -> list[str]:
    others = [c for c in pool if c != correct]
    return random.sample(others, k=min(n, len(others)))


def _build_options(
    correct: str, label_for: Callable[[str], str], pool: list[str] | None = None
) -> tuple[list[Option], str]:
    pool = pool or data.all_codes()
    distractors = _sample_distractors(correct, pool, OPTIONS_PER_QUESTION - 1)
    codes = [correct, *distractors]
    random.shuffle(codes)
    return [Option(code=c, label=label_for(c)) for c in codes], correct


def _explain(code: str, lang: str) -> str:
    entry = data.get(code)
    return t(
        "quiz.explanation",
        lang,
        letter=code,
        name=t(f"mcs65.name.{code}", lang),
        morse=entry.morse,
        meaning=t(f"mcs65.meaning.{code}", lang),
    )


class _BaseMcs65Trainer(Trainer):
    subject = SUBJECT_CODE

    def all_entry_codes(self) -> list[str]:
        return data.all_codes()


class FlagToLetterTrainer(_BaseMcs65Trainer):
    key = "mcs65.flag_to_letter"
    topic = "flags"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.flag_to_letter", lang),
            prompt_image_path=flag_renderer.render(entry_code),
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class LetterToFlagTrainer(_BaseMcs65Trainer):
    """Show a letter, list candidate codes as buttons; the user picks which letter has the right flag.

    The flag itself can't fit on a Telegram button, so we phrase the question as
    «Какой флаг соответствует букве X?» and list 4 letter codes; the user is
    visualising the flags mentally. After the answer we send the correct flag image.
    """

    key = "mcs65.letter_to_flag"
    topic = "flags"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_flag", lang, letter=entry_code),
            prompt_image_path=flag_renderer.render_letter_card(entry_code),
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class LetterToNameTrainer(_BaseMcs65Trainer):
    key = "mcs65.letter_to_name"
    topic = "names"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(
            entry_code, lambda c: t(f"mcs65.name.{c}", lang)
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_name", lang, letter=entry_code),
            prompt_image_path=None,
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class NameToLetterTrainer(_BaseMcs65Trainer):
    key = "mcs65.name_to_letter"
    topic = "names"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t(
                "quiz.prompt.name_to_letter",
                lang,
                name=t(f"mcs65.name.{entry_code}", lang),
            ),
            prompt_image_path=None,
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class LetterToMorseTrainer(_BaseMcs65Trainer):
    key = "mcs65.letter_to_morse"
    topic = "morse"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(
            entry_code, lambda c: data.get(c).morse
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_morse", lang, letter=entry_code),
            prompt_image_path=None,
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class MorseToLetterTrainer(_BaseMcs65Trainer):
    key = "mcs65.morse_to_letter"
    topic = "morse"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t(
                "quiz.prompt.morse_to_letter", lang, morse=data.get(entry_code).morse
            ),
            prompt_image_path=None,
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class LetterToMeaningTrainer(_BaseMcs65Trainer):
    key = "mcs65.letter_to_meaning"
    topic = "signals"

    def build_question(self, entry_code: str, lang: str) -> Question:
        # Meanings are long; keep button labels short so mobile inline keyboards stay readable.
        def _label(code: str) -> str:
            full = t(f"mcs65.meaning.{code}", lang)
            return full if len(full) <= 60 else full[:57] + "…"

        options, correct = _build_options(entry_code, _label)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_meaning", lang, letter=entry_code),
            prompt_image_path=flag_renderer.render(entry_code),
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


class MeaningToLetterTrainer(_BaseMcs65Trainer):
    key = "mcs65.meaning_to_letter"
    topic = "signals"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t(
                "quiz.prompt.meaning_to_letter",
                lang,
                meaning=t(f"mcs65.meaning.{entry_code}", lang),
            ),
            prompt_image_path=None,
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


def register() -> None:
    """Register all МСС-65 topics and trainers."""

    registry.register_topic(
        subject=SUBJECT_CODE,
        code="flags",
        title_i18n_key="menu.topic.flags",
        intro_i18n_key="menu.topic_intro.flags",
        order=1,
    )
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="names",
        title_i18n_key="menu.topic.names",
        intro_i18n_key="menu.topic_intro.names",
        order=2,
    )
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="morse",
        title_i18n_key="menu.topic.morse",
        intro_i18n_key="menu.topic_intro.morse",
        order=3,
    )
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="signals",
        title_i18n_key="menu.topic.signals",
        intro_i18n_key="menu.topic_intro.signals",
        order=4,
    )
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="letters",
        title_i18n_key="menu.topic.letters",
        intro_i18n_key="menu.topic_intro.letters",
        order=5,
    )

    registry.register_trainer(FlagToLetterTrainer())
    registry.register_trainer(LetterToFlagTrainer())
    registry.register_trainer(LetterToNameTrainer())
    registry.register_trainer(NameToLetterTrainer())
    registry.register_trainer(LetterToMorseTrainer())
    registry.register_trainer(MorseToLetterTrainer())
    registry.register_trainer(LetterToMeaningTrainer())
    registry.register_trainer(MeaningToLetterTrainer())

    # The "letters" topic borrows trainers from all the others — it's a mixed-mode
    # drill rather than its own trainer family. We register references to existing
    # trainers under the new topic via a thin wrapper.
    for tr in [
        FlagToLetterTrainer,
        LetterToNameTrainer,
        NameToLetterTrainer,
        LetterToMorseTrainer,
        MorseToLetterTrainer,
    ]:
        registry.get_topic(SUBJECT_CODE, "letters").trainers.append(
            registry.get_trainer(tr.key)
        )
