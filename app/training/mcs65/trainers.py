"""Concrete МСС-65 trainers and topic registration."""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

from app.i18n import t, t_list
from app.training.base import Option, Question, Trainer
from app.training.mcs65 import data, flag_renderer, pennant_renderer, pennants
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


def _build_options_from_labels(
    correct_code: str, correct_label: str, distractor_labels: list[str]
) -> list[Option]:
    """Options where distractor labels are arbitrary strings, not derived from codes.

    Used by phonetics trainer — distractors are «sound-alike» words that don't
    belong to any МСС letter, so they get placeholder codes that can never
    match `correct_code`. Falls back to no distractors if the pool is empty.
    """
    picks = random.sample(
        distractor_labels, k=min(OPTIONS_PER_QUESTION - 1, len(distractor_labels))
    )
    items = [(correct_code, correct_label)] + [(f"_{i}", label) for i, label in enumerate(picks)]
    random.shuffle(items)
    return [Option(code=c, label=l) for c, l in items]


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

    def build_answer_image(self, entry_code: str) -> Path | None:
        # Always reinforce with the correct letter's flag in the result message.
        return flag_renderer.render(entry_code)


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


def _build_visual_grid_options(
    correct: str,
    pool: list[str],
    image_for: Callable[[str], Path],
) -> tuple[list[Option], bytes]:
    """Pick 3 distractors, shuffle with the correct entry, render a 2×2 numbered grid.

    Returns (options, grid_png_bytes). Each option's `code` is the entry placed
    in that slot; the `label` is the position number 1–4. The user picks a
    position, the callback carries the underlying entry code, so the existing
    correct-match logic works without changes.
    """
    distractors = _sample_distractors(correct, pool, OPTIONS_PER_QUESTION - 1)
    codes = [correct, *distractors]
    random.shuffle(codes)
    paths = [image_for(c) for c in codes]
    grid_bytes = flag_renderer.compose_numbered_grid(paths)
    options = [Option(code=c, label=str(i + 1)) for i, c in enumerate(codes)]
    return options, grid_bytes


class LetterToFlagTrainer(_BaseMcs65Trainer):
    """Show a letter, present 4 flag images in a 2×2 grid, the user picks by number."""

    key = "mcs65.letter_to_flag"
    topic = "flags"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, grid = _build_visual_grid_options(
            entry_code, data.all_codes(), flag_renderer.render
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_flag", lang, letter=entry_code),
            prompt_image_path=None,
            prompt_image_bytes=grid,
            options=options,
            correct_code=entry_code,
            explanation=_explain(entry_code, lang),
        )

    def build_answer_image(self, entry_code: str) -> Path | None:
        return flag_renderer.render(entry_code)


class LetterToNameTrainer(_BaseMcs65Trainer):
    """Phonetic alphabet drill — distractors are curated «sound-alike» words
    starting with the same letter as the correct name, so the answer can't be
    guessed from the initial Cyrillic letter alone.
    """

    key = "mcs65.letter_to_name"
    topic = "names"

    def build_question(self, entry_code: str, lang: str) -> Question:
        correct_name = t(f"mcs65.name.{entry_code}", lang)
        distractor_pool = t_list(f"mcs65.name_distractors.{entry_code}", lang)
        if len(distractor_pool) < OPTIONS_PER_QUESTION - 1:
            # Defensive fallback to the old behaviour — only kicks in if the
            # locale is missing distractors for some entry.
            distractor_pool = [
                t(f"mcs65.name.{c}", lang) for c in data.all_codes() if c != entry_code
            ]
        options = _build_options_from_labels(entry_code, correct_name, distractor_pool)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.letter_to_name", lang, letter=entry_code),
            prompt_image_path=flag_renderer.render_text_card(entry_code),
            options=options,
            correct_code=entry_code,
            correct_label=correct_name,
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
            prompt_image_path=flag_renderer.render_text_card(
                t(f"mcs65.name.{entry_code}", lang)
            ),
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
            prompt_image_path=flag_renderer.render_text_card(entry_code),
            options=options,
            correct_code=correct,
            correct_label=data.get(entry_code).morse,
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
            prompt_image_path=flag_renderer.render_text_card(data.get(entry_code).morse),
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
            correct_label=_label(entry_code),
            explanation=_explain(entry_code, lang),
        )


class MeaningToLetterTrainer(_BaseMcs65Trainer):
    key = "mcs65.meaning_to_letter"
    topic = "signals"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(entry_code, lambda c: c)
        meaning = t(f"mcs65.meaning.{entry_code}", lang)
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.meaning_to_letter", lang, meaning=meaning),
            prompt_image_path=flag_renderer.render_text_card(meaning),
            options=options,
            correct_code=correct,
            explanation=_explain(entry_code, lang),
        )


def _explain_pennant(code: str, lang: str) -> str:
    return t(
        "quiz.explanation_pennant",
        lang,
        label=t(f"mcs65.pennant_name.{code}", lang),
        description=t(f"mcs65.pennant_meaning.{code}", lang),
    )


def _explain_numeral(code: str, lang: str) -> str:
    entry = pennants.get(code)
    digit = entry.short_label
    return t(
        "quiz.explanation_numeral",
        lang,
        digit=digit,
        name=t(f"mcs65.pennant_name.{code}", lang),
        morse=entry.morse or "—",
    )


class _BasePennantTrainer(Trainer):
    subject = SUBJECT_CODE
    topic = "pennants"

    def all_entry_codes(self) -> list[str]:
        return pennants.all_codes()

    def build_answer_image(self, entry_code: str) -> Path | None:
        return pennant_renderer.render(entry_code)


class PennantToNameTrainer(_BasePennantTrainer):
    key = "mcs65.pennant_to_name"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, correct = _build_options(
            entry_code,
            lambda c: t(f"mcs65.pennant_label.{c}", lang),
            pool=pennants.all_codes(),
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.pennant_to_name", lang),
            prompt_image_path=pennant_renderer.render(entry_code),
            options=options,
            correct_code=correct,
            correct_label=t(f"mcs65.pennant_label.{entry_code}", lang),
            explanation=_explain_pennant(entry_code, lang),
        )


class NameToPennantTrainer(_BasePennantTrainer):
    """Show the pennant name, present a 2×2 grid of pennant images, user picks by number."""

    key = "mcs65.name_to_pennant"

    def build_question(self, entry_code: str, lang: str) -> Question:
        options, grid = _build_visual_grid_options(
            entry_code, pennants.all_codes(), pennant_renderer.render
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t(
                "quiz.prompt.name_to_pennant",
                lang,
                name=t(f"mcs65.pennant_name.{entry_code}", lang),
            ),
            prompt_image_path=None,
            prompt_image_bytes=grid,
            options=options,
            correct_code=entry_code,
            explanation=_explain_pennant(entry_code, lang),
        )

    def build_answer_image(self, entry_code: str) -> Path | None:
        return pennant_renderer.render(entry_code)


class NumeralToMorseTrainer(_BasePennantTrainer):
    key = "mcs65.numeral_to_morse"

    def all_entry_codes(self) -> list[str]:
        return pennants.numeral_codes()

    def build_question(self, entry_code: str, lang: str) -> Question:
        entry = pennants.get(entry_code)
        options, correct = _build_options(
            entry_code,
            lambda c: pennants.get(c).morse or "—",
            pool=pennants.numeral_codes(),
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.numeral_to_morse", lang, digit=entry.short_label),
            prompt_image_path=flag_renderer.render_text_card(entry.short_label),
            options=options,
            correct_code=correct,
            correct_label=entry.morse or "—",
            explanation=_explain_numeral(entry_code, lang),
        )


class MorseToNumeralTrainer(_BasePennantTrainer):
    key = "mcs65.morse_to_numeral"

    def all_entry_codes(self) -> list[str]:
        return pennants.numeral_codes()

    def build_question(self, entry_code: str, lang: str) -> Question:
        entry = pennants.get(entry_code)
        options, correct = _build_options(
            entry_code,
            lambda c: pennants.get(c).short_label,
            pool=pennants.numeral_codes(),
        )
        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=t("quiz.prompt.morse_to_numeral", lang, morse=entry.morse),
            prompt_image_path=flag_renderer.render_text_card(entry.morse or "—"),
            options=options,
            correct_code=correct,
            explanation=_explain_numeral(entry_code, lang),
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
        code="pennants",
        title_i18n_key="menu.topic.pennants",
        intro_i18n_key="menu.topic_intro.pennants",
        order=5,
    )
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="letters",
        title_i18n_key="menu.topic.letters",
        intro_i18n_key="menu.topic_intro.letters",
        order=6,
    )

    registry.register_trainer(FlagToLetterTrainer())
    registry.register_trainer(LetterToFlagTrainer())
    registry.register_trainer(LetterToNameTrainer())
    registry.register_trainer(NameToLetterTrainer())
    registry.register_trainer(LetterToMorseTrainer())
    registry.register_trainer(MorseToLetterTrainer())
    registry.register_trainer(LetterToMeaningTrainer())
    registry.register_trainer(MeaningToLetterTrainer())
    registry.register_trainer(PennantToNameTrainer())
    registry.register_trainer(NameToPennantTrainer())
    registry.register_trainer(NumeralToMorseTrainer())
    registry.register_trainer(MorseToNumeralTrainer())

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
