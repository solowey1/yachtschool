"""Reference (theory) page builder.

Each section is rendered top-down from i18n strings + the canonical data
modules — so adding a language or fixing a typo in one place updates the
reference automatically.
"""

from __future__ import annotations

from app.i18n import t
from app.training.mcs65 import data, pennants


def _row_simple(a: str, b: str, lang: str) -> str:
    return t("reference.row_simple", lang, a=a, b=b)


def _row_morse(a: str, b: str, lang: str) -> str:
    return t("reference.row_morse", lang, a=a, b=b)


def _names_table(lang: str) -> str:
    return "".join(
        _row_simple(code, t(f"mcs65.name.{code}", lang), lang) for code in data.all_codes()
    )


def _morse_letters_table(lang: str) -> str:
    return "".join(_row_morse(code, data.get(code).morse, lang) for code in data.all_codes())


def _morse_digits_table(lang: str) -> str:
    return "".join(
        _row_morse(pennants.get(code).short_label, pennants.get(code).morse or "—", lang)
        for code in pennants.numeral_codes()
    )


def _signals_table(lang: str) -> str:
    return "".join(
        _row_simple(code, t(f"mcs65.meaning.{code}", lang), lang) for code in data.all_codes()
    )


def _numerals_table(lang: str) -> str:
    return "".join(
        _row_simple(
            pennants.get(code).short_label,
            t(f"mcs65.pennant_name.{code}", lang),
            lang,
        )
        for code in pennants.numeral_codes()
    )


def build_reference_text(section: str, lang: str) -> str:
    if section == "about":
        return t("reference.about", lang)
    if section == "flags":
        return t("reference.flags_intro", lang) + "\n\n" + _names_table(lang)
    if section == "names":
        return t("reference.names_intro", lang) + _names_table(lang)
    if section == "morse":
        return (
            t("reference.morse_intro", lang)
            + _morse_letters_table(lang)
            + t("reference.morse_digits", lang)
            + _morse_digits_table(lang)
        )
    if section == "signals":
        return t("reference.signals_intro", lang) + _signals_table(lang)
    if section == "pennants":
        return t("reference.pennants_intro", lang) + _numerals_table(lang)
    if section == "substitutes":
        return t("reference.substitutes_intro", lang)
    return t("common.error", lang)
