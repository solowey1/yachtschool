from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import NavCB, NextCB, RefCB, TopicCB
from app.i18n import t
from app.training.registry import registry

# All reference sections live here so we don't sprinkle the codes across handlers.
REFERENCE_SECTIONS: tuple[str, ...] = (
    "about",
    "flags",
    "names",
    "morse",
    "signals",
    "pennants",
    "substitutes",
)


def _btn(label: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=callback)


def main_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.section.reference", lang), NavCB(target="reference").pack())],
            [_btn(t("menu.section.training", lang), NavCB(target="training").pack())],
            [_btn(t("menu.section.stats", lang), NavCB(target="stats").pack())],
        ]
    )


def training_menu(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for topic in registry.topics():
        rows.append(
            [
                _btn(
                    t(topic.title_i18n_key, lang),
                    TopicCB(subject=topic.subject, topic=topic.code).pack(),
                )
            ]
        )
    rows.append([_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_menu(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t(f"reference.section.{code}", lang), RefCB(section=code).pack())]
        for code in REFERENCE_SECTIONS
    ]
    rows.append([_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.back_to_section", lang), NavCB(target="reference").pack())]
        ]
    )


def stats_back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())]
        ]
    )


def quiz_answer_keyboard(question, *, mode: str = "i") -> InlineKeyboardMarkup:
    from app.bot.callbacks import AnswerCB

    rows: list[list[InlineKeyboardButton]] = []
    for opt in question.options:
        cb = AnswerCB(
            trainer=question.trainer_key,
            entry=question.entry_code,
            chosen=opt.code,
            correct=question.correct_code,
            mode=mode,
        )
        rows.append([_btn(opt.label, cb.pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_next_keyboard(topic: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("common.next_question", lang), NextCB(topic=topic).pack())],
            [_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())],
        ]
    )


def daily_result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())]
        ]
    )
