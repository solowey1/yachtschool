from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import (
    ColregsCB,
    DonateCB,
    NavCB,
    NextCB,
    PauseCB,
    RefCB,
    RefDetailCB,
    SettingsCB,
    TopicCB,
)
from app.services.user_settings import PAUSE_PRESETS
from app.training.colregs.reference_data import (
    CHAPTER_ORDER,
    CHAPTER_RULES,
    display_label as colregs_display_label,
)
from app.i18n import t, translator
from app.training.mcs65 import data as mcs65_data
from app.training.mcs65 import pennants as mcs65_pennants
from app.training.registry import registry

# Picker presets — small and curated, not «every possible value».
COUNT_PRESETS: tuple[int, ...] = (1, 3, 5, 7, 10)
HOUR_PRESETS: tuple[str, ...] = tuple(f"{h:02d}:00" for h in range(24))

# Reference top-level layout for МСС-65 (matches what existed before subject
# nesting was introduced).
MCS65_REFERENCE_SECTIONS: tuple[str, ...] = (
    "about",
    "flags",
    "names",
    "morse",
    "signals",
    "pennants",
    "substitutes",
)

# Subjects offered in both Training and Reference menus. Order = menu order.
SUBJECTS: tuple[str, ...] = ("colregs", "mcs65")


def _btn(label: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=callback)


def _chunk(items: list, size: int) -> list[list]:
    """Chunk into rows of `size`. If the trailing partial row has fewer than
    half-size buttons, merge it into the previous row so layouts stay tidy
    (no «one lonely button» last rows).
    """
    rows = [items[i : i + size] for i in range(0, len(items), size)]
    if len(rows) >= 2 and len(rows[-1]) <= size // 2:
        rows[-2].extend(rows.pop())
    return rows


# ── Main / settings ──────────────────────────────────────────────────────────

DONATE_AMOUNTS: tuple[int, ...] = (50, 100, 250, 500, 1000)


def main_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.section.reference", lang), NavCB(target="reference").pack())],
            [_btn(t("menu.section.training", lang), NavCB(target="training").pack())],
            [_btn(t("menu.section.stats", lang), NavCB(target="stats").pack())],
            [_btn(t("menu.section.settings", lang), NavCB(target="settings").pack())],
            [_btn(t("menu.section.donate", lang), NavCB(target="donate").pack())],
        ]
    )


def donate_menu(lang: str) -> InlineKeyboardMarkup:
    amounts_row = [
        _btn(f"{n} ⭐", DonateCB(amount=n).pack()) for n in DONATE_AMOUNTS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            amounts_row,
            [_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())],
        ]
    )


# ── Pause daily delivery ─────────────────────────────────────────────────────

def daily_header_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Single «⏸ Сделать паузу» button pinned to the daily-batch header."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("pause.btn_open", lang), PauseCB(action="open_header").pack())]
        ]
    )


def pause_duration_picker(lang: str, *, from_header: bool) -> InlineKeyboardMarkup:
    """1/3/7/14/30 in one row, «Навсегда» below, then back/cancel.

    `from_header=True` means the picker replaced the daily header — cancel
    should restore it. `from_header=False` means it came from Settings —
    cancel returns to the settings root.
    """
    top = [_btn(str(n), PauseCB(action="pick", days=n).pack()) for n in PAUSE_PRESETS]
    rows = [
        top,
        [_btn(t("pause.btn_forever", lang), PauseCB(action="pick", days=0).pack())],
    ]
    if from_header:
        rows.append([_btn(t("pause.btn_cancel", lang), PauseCB(action="cancel_hdr").pack())])
    else:
        rows.append(
            [_btn(t("menu.back_to_section", lang), NavCB(target="settings").pack())]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pause_settings_view(lang: str, *, is_paused: bool) -> InlineKeyboardMarkup:
    """From Settings → «⏸ Пауза». Shows either «pick duration» controls or,
    when the user is already paused, a «Возобновить» button plus the same
    picker (in case they want to extend or shorten).
    """
    rows: list[list[InlineKeyboardButton]] = []
    if is_paused:
        rows.append(
            [_btn(t("pause.btn_unpause", lang), PauseCB(action="unpause").pack())]
        )
    top = [_btn(str(n), PauseCB(action="pick", days=n).pack()) for n in PAUSE_PRESETS]
    rows.append(top)
    rows.append(
        [_btn(t("pause.btn_forever", lang), PauseCB(action="pick", days=0).pack())]
    )
    rows.append(
        [_btn(t("menu.back_to_section", lang), NavCB(target="settings").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    rows.append(
        [_btn(t("settings.btn_pause", lang), PauseCB(action="view").pack())]
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
        [_btn(t("menu.back_to_section", lang), NavCB(target="settings").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_count_picker(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(str(n), SettingsCB(action="set", field="count", value=str(n)).pack())
            for n in COUNT_PRESETS
        ],
        [_btn(t("settings.btn_reset", lang), SettingsCB(action="reset", field="count").pack())],
        [_btn(t("menu.back_to_section", lang), NavCB(target="settings").pack())],
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
                    SettingsCB(
                        action="set", field="time", value=HOUR_PRESETS[r * 6 + c].replace(":", "")
                    ).pack(),
                )
                for c in range(6)
            ]
        )
    rows.append([_btn(t("settings.btn_reset", lang), SettingsCB(action="reset", field="time").pack())])
    rows.append(
        [_btn(t("menu.back_to_section", lang), NavCB(target="settings").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())]
        ]
    )


# ── Training ─────────────────────────────────────────────────────────────────

def training_subject_picker(lang: str) -> InlineKeyboardMarkup:
    """Subject picker: МППСС-72 then МСС-65, then back."""
    rows = [
        [
            _btn(
                t(f"menu.subject.{subject}", lang),
                NavCB(target="training", subject=subject).pack(),
            )
        ]
        for subject in SUBJECTS
    ]
    rows.append([_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def colregs_submenu(lang: str) -> InlineKeyboardMarkup:
    """Single-trainer subject — instead of a topic list, give the user a
    start / settings split. Keeps trainer config a click away from the
    «launch» button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t("colregs.btn_start", lang), ColregsCB(action="start").pack())],
            [_btn(t("colregs.btn_settings", lang), ColregsCB(action="settings").pack())],
            [_btn(t("menu.back_to_section", lang), NavCB(target="training").pack())],
        ]
    )


VESSEL_TYPE_CODES: tuple[str, ...] = ("sail", "motor", "fishing", "nuc", "ram")


def colregs_settings(lang: str, *, night_mode: bool, enabled_types: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    night_label = t(
        "colregs.mode_row",
        lang,
        value=t("colregs.mode_night" if night_mode else "colregs.mode_day", lang),
    )
    rows.append(
        [_btn(night_label, ColregsCB(action="toggle_night").pack())]
    )

    for code in VESSEL_TYPE_CODES:
        is_on = code in enabled_types
        label = t(
            "colregs.type_row",
            lang,
            mark="✅" if is_on else "⬜",
            name=t(f"colregs.vessel_type.{code}", lang),
        )
        rows.append(
            [_btn(label, ColregsCB(action="toggle_type", value=code).pack())]
        )

    rows.append([_btn(t("menu.back_to_section", lang), ColregsCB(action="menu").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def training_topics(lang: str, subject: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for topic in registry.topics(subject=subject):
        rows.append(
            [
                _btn(
                    t(topic.title_i18n_key, lang),
                    TopicCB(subject=topic.subject, topic=topic.code).pack(),
                )
            ]
        )
    rows.append(
        [_btn(t("menu.back_to_section", lang), NavCB(target="training").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Reference: subject picker + per-subject section lists ────────────────────

def reference_subject_picker(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                t(f"menu.subject.{subject}", lang),
                NavCB(target="reference", subject=subject).pack(),
            )
        ]
        for subject in SUBJECTS
    ]
    rows.append([_btn(t("menu.back_to_main", lang), NavCB(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_mcs65_menu(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t(f"reference.section.{code}", lang), RefCB(subject="mcs65", section=code).pack())]
        for code in MCS65_REFERENCE_SECTIONS
    ]
    rows.append(
        [_btn(t("menu.back_to_section", lang), NavCB(target="reference").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_colregs_menu(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                t(f"reference.colregs.section.{code}", lang),
                RefCB(subject="colregs", section=code).pack(),
            )
        ]
        for code in CHAPTER_ORDER
    ]
    rows.append(
        [_btn(t("menu.back_to_section", lang), NavCB(target="reference").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_colregs_part(lang: str, chapter: str) -> InlineKeyboardMarkup:
    """Buttons for individual rules inside a COLREGs chapter, 5 per row.

    Annexes (a1..a4) display as Roman numerals; regular rules as «1», «14», …
    """
    rules = CHAPTER_RULES.get(chapter, [])
    rows: list[list[InlineKeyboardButton]] = []
    for chunk in _chunk(rules, 5):
        rows.append(
            [
                _btn(
                    colregs_display_label(r),
                    RefCB(subject="colregs", section=chapter, item=r).pack(),
                )
                for r in chunk
            ]
        )
    rows.append(
        [
            _btn(
                t("menu.back_to_section", lang),
                NavCB(target="reference", subject="colregs").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_back_to_part(lang: str, chapter: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(
                    t("menu.back_to_section", lang),
                    RefCB(subject="colregs", section=chapter).pack(),
                )
            ]
        ]
    )


# ── Reference (МСС-65 drill-down: same as before, just with subject="mcs65") ──

def reference_section_keyboard(section: str, lang: str) -> InlineKeyboardMarkup:
    """Buttons shown alongside the МСС-65 section's text. Flags / numerals
    / substitutes each expose drill-down buttons; other sections only have
    a back button.
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

    rows.append(
        [
            _btn(
                t("menu.back_to_section", lang),
                NavCB(target="reference", subject="mcs65").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reference_detail_back(section: str, lang: str) -> InlineKeyboardMarkup:
    """Back button on a McCs-65 detail page — returns to the section list."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(
                    t("menu.back_to_section", lang),
                    RefCB(subject="mcs65", section=section).pack(),
                )
            ]
        ]
    )


# ── Quiz ─────────────────────────────────────────────────────────────────────

POSITION_LETTERS: tuple[str, ...] = ("A", "B", "C", "D")
#: Magic value for AnswerCB.chosen indicating the user pressed «Показать ответ».
#: Doesn't collide with any real entry code (those are letters / Nx / Sx / AP /
#: _dN distractors / opt_N for COLREGs).
SKIP_CODE = "_skip"


def quiz_answer_keyboard(question, *, mode: str = "i", lang: str = "ru") -> InlineKeyboardMarkup:
    """Two rows: «🤷 Показать ответ» on top, then A/B/C/D answer buttons.

    Option labels live in the message caption (or, for grid trainers, on
    the rendered image itself) — buttons stay compact regardless of how
    long the answer texts are.
    """
    from app.bot.callbacks import AnswerCB

    skip_cb = AnswerCB(
        trainer=question.trainer_key,
        entry=question.entry_code,
        chosen=SKIP_CODE,
        correct=question.correct_code,
        mode=mode,
    )
    rows: list[list[InlineKeyboardButton]] = [
        [_btn(t("quiz.show_answer", lang), skip_cb.pack())]
    ]

    answer_row: list[InlineKeyboardButton] = []
    for i, opt in enumerate(question.options[: len(POSITION_LETTERS)]):
        cb = AnswerCB(
            trainer=question.trainer_key,
            entry=question.entry_code,
            chosen=opt.code,
            correct=question.correct_code,
            mode=mode,
        )
        answer_row.append(_btn(POSITION_LETTERS[i], cb.pack()))
    rows.append(answer_row)
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
