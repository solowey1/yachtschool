"""COLREGs-72 trainer — encounter situation recognition."""

from __future__ import annotations

import random

from app.training.base import Option, Question, Trainer
from app.training.colregs.data import (
    SCENARIO_CODES,
    SUBJECT_CODE,
    generate_for_code,
)
from app.training.colregs.renderer import render_scenario
from app.training.registry import registry


class ColregsTrainer(Trainer):
    """Presents a random encounter scenario image and asks who gives way."""

    key = "colregs.encounter"
    subject = SUBJECT_CODE
    topic = "encounter"

    def all_entry_codes(self) -> list[str]:
        return list(SCENARIO_CODES)

    def build_question(self, entry_code: str, lang: str) -> Question:
        scenario = generate_for_code(entry_code)
        png_bytes = render_scenario(scenario)

        # Shuffle answers: correct + 3 wrong
        answers = [(scenario.correct_answer, True)] + [
            (w, False) for w in scenario.wrong_answers[:3]
        ]
        random.shuffle(answers)

        options = []
        correct_code = entry_code  # will be overridden below
        for i, (text, is_correct) in enumerate(answers):
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

    def build_answer_image(self, entry_code: str) -> None:
        # No separate answer image — the question image stays, rule text is explanation
        return None


def register() -> None:
    """Register COLREGs topic and trainer."""
    registry.register_topic(
        subject=SUBJECT_CODE,
        code="encounter",
        title_i18n_key="menu.topic.colregs_encounter",
        intro_i18n_key="menu.topic_intro.colregs_encounter",
        order=1,
    )
    registry.register_trainer(ColregsTrainer())
