"""Builds the Morse mnemonic-chants reference page.

The chant strings («напевы») come from i18n (mcs65.morse_mnemonic.<letter>);
the dot/dash codes come from the single source of truth in mcs65.data. The
table is rendered as a <pre> block so letters, codes and chants align.
"""

from __future__ import annotations

from app.i18n import t
from app.training.mcs65 import data


def _display_code(morse: str) -> str:
    """«.-» → «·–» for a nicer, more legible code column."""
    return morse.replace(".", "·").replace("-", "–")


def build_text(lang: str) -> str:
    rows = []
    for letter in data.all_codes():
        code = _display_code(data.get(letter).morse)
        chant = t(f"mcs65.morse_mnemonic.{letter}", lang)
        rows.append(f"{letter}  {code.ljust(5)}  {chant}")
    table = "<pre>" + "\n".join(rows) + "</pre>"
    return (
        t("morse.mnemonics_intro", lang)
        + "\n\n"
        + t("morse.mnemonics_table_header", lang)
        + "\n"
        + table
    )
