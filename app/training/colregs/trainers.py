"""МППСС-72 (COLREGs) trainer — encounter situation recognition."""

from __future__ import annotations

import random

from app.training.base import Option, Question, Trainer
from app.training.colregs.data import SCENARIO_CODES, SUBJECT_CODE, generate_for_code
from app.training.colregs.renderer import render_scenario
from app.training.registry import registry


def _shuffle_deterministic(items: list, seed: str) -> list:
    """Like random.shuffle, but doesn't perturb the global random state.

    The seed (typically the entry_code) makes the answer order stable across
    rebuilds — the result message looks up the right option text when it
    rebuilds the question for the explanation.
    """
    state = random.getstate()
    random.seed(seed)
    try:
        shuffled = list(items)
        random.shuffle(shuffled)
        return shuffled
    finally:
        random.setstate(state)


class ColregsTrainer(Trainer):
    """One trainer per encounter type variant — same code → same scene → same answers."""

    key = "colregs.encounter"
    subject = SUBJECT_CODE
    topic = "encounter"

    def all_entry_codes(self) -> list[str]:
        return list(SCENARIO_CODES)

    def build_question(
        self, entry_code: str, lang: str, *, night_mode: bool = False
    ) -> Question:
        scenario = generate_for_code(entry_code)
        png_bytes = render_scenario(scenario, mode="night" if night_mode else "day")

        # 1 correct + up to 3 distractors, shuffled deterministically per code.
        labelled = [(scenario.correct_answer, True)] + [
            (w, False) for w in scenario.wrong_answers[:3]
        ]
        labelled = _shuffle_deterministic(labelled, f"{entry_code}#shuffle")

        options: list[Option] = []
        correct_code = "opt_0"
        for i, (text, is_correct) in enumerate(labelled):
            code = f"opt_{i}"
            if is_correct:
                correct_code = code
            options.append(Option(code=code, label=text))

        return Question(
            trainer_key=self.key,
            subject=self.subject,
            topic=self.topic,
            entry_code=entry_code,
            prompt_text=scenario.question,
            prompt_image_path=None,
            prompt_image_bytes=png_bytes,
            options=options,
            correct_code=correct_code,
            correct_label=scenario.correct_answer,
            explanation=scenario.rule_text,
        )

    def build_answer_image(self, entry_code: str):
        # Question image already shows the scene; no separate answer reveal.
        return None


def register() -> None:
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="encounter",
        title_i18n_key="menu.topic.colregs_encounter",
        intro_i18n_key="menu.topic_intro.colregs_encounter",
        order=1,
    )
    registry.register_trainer(ColregsTrainer())
