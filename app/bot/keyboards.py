from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import NavCB, NextCB, RefCB, RefDetailCB, SettingsCB, TopicCB
from app.i18n import t, translator
from app.training.mcs65 import data as mcs65_data
from app.training.mcs65 import pennants as mcs65_pennants
from app.training.registry import registry

# Picker presets — small and curated, not «every possible value».
COUNT_PRESETS: tuple[int, ...] = (1, 3, 5, 7, 10)
HOUR_PRESETS: tuple[str, ...] = tuple(f"{h:02d}:00" for h in range(24))

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
            [_btn(t("menu.section.settings", lang), NavCB(target="settings").pack())],
        ]
    )


def settings_root(lang: str, *, language_pickable: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if language_pickable:
        rows.append(
            [_btn(t("settings.btn_lang", lang), SettingsCB(action="view", field="lang").pack())]
        )
    rows.append(
        [_btn(t("settings.btn_count", lang), SettingsCB(action="view", field="count").pack())]
    )
    rows.append(
        [_btn(t("settings.btn_time", lang), SettingsCB(action="view", field="time").pack())]
    )
    rows.append([_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_lang_picker(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                t(f"settings.lang_name.{code}", lang) or code.upper(),
                SettingsCB(action="set", field="lang", value=code).pack(),
            )
        ]
        for code in translator().available_languages()
    ]
    rows.append(
        [_btn(t("menu.back_to_section", lang), SettingsCB(action="view", field="").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_count_picker(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(str(n), SettingsCB(action="set", field="count", value=str(n)).pack())
            for n in COUNT_PRESETS
        ],
        [_btn(t("settings.btn_reset", lang), SettingsCB(action="reset", field="count").pack())],
        [_btn(t("menu.back_to_section", lang), SettingsCB(action="view", field="").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_time_picker(lang: str) -> InlineKeyboardMarkup:
    """24 UTC hours laid out as 4 rows × 6 columns + reset + back."""
    rows: list[list[InlineKeyboardButton]] = []
    for r in range(4):
        rows.append(
            [
                _btn(
                    HOUR_PRESETS[r * 6 + c],
                    # CallbackData uses ":" as a separator — encode as HHMM here.
                    SettingsCB(
                        action="set", field="time", value=HOUR_PRESETS[r * 6 + c].replace(":", "")
                    ).pack(),
                )
                for c in range(6)
            ]
        )
    rows.append([_btn(t("settings.btn_reset", lang), SettingsCB(action="reset", field="time").pack())])
    rows.append(
        [_btn(t("menu.back_to_section", lang), SettingsCB(action="view", field="").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def _chunk(items: list, size: int) -> list[list]:
    """Chunk into rows of `size`. If the trailing partial row has fewer than
    half-size buttons, merge it into the previous row so layouts stay tidy
    (no «one lonely button» last rows).
    """
    rows = [items[i : i + size] for i in range(0, len(items), size)]
    if len(rows) >= 2 and len(rows[-1]) <= size // 2:
        rows[-2].extend(rows.pop())
    return rows


def reference_section_keyboard(section: str, lang: str) -> InlineKeyboardMarkup:
    """Buttons shown alongside the section's text. Flags / numerals / substitutes
    each expose drill-down buttons; other sections only have a back button.
    """
    rows: list[list[InlineKeyboardButton]] = []

    if section == "flags":
        codes = mcs65_data.all_codes()
        for chunk in _chunk(codes, 5):
            rows.append([_btn(c, RefDetailCB(code=c).pack()) for c in chunk])
    elif section == "pennants":
        for chunk in _chunk(mcs65_pennants.numeral_codes(), 5):
            rows.append(
                [_btn(mcs65_pennants.get(c).short_label, RefDetailCB(code=c).pack()) for c in chunk]
            )
    elif section == "substitutes":
        sub_codes = ["S1", "S2", "S3"]
        rows.append(
            [
                _btn(t(f"mcs65.pennant_label.{c}", lang), RefDetailCB(code=c).pack())
                for c in sub_codes
            ]
        )
        rows.append([_btn(t("mcs65.pennant_label.AP", lang), RefDetailCB(code="AP").pack())])

    rows.append([_btn(t("menu.back_to_section", lang), NavCB(target="reference").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_detail_back(section: str, lang: str) -> InlineKeyboardMarkup:
    """Back button on a detail page — returns to the section that owns the entry."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.back_to_section", lang), RefCB(section=section).pack())]
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
