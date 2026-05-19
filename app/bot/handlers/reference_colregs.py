"""МППСС-72 reference content builder.

The static structure (chapter → rule numbers) lives in
`app/training/colregs/reference_data.py` so it's importable from keyboards
without pulling in handler code. This module is just the text-rendering
side — it pairs each chapter/rule with its i18n string.
"""

from __future__ import annotations

from app.i18n import t
from app.training.colregs.reference_data import CHAPTER_ORDER, CHAPTER_RULES  # re-export


__all__ = [
    "CHAPTER_ORDER",
    "CHAPTER_RULES",
    "about_text",
    "chapter_intro",
    "rule_text",
]


def chapter_intro(chapter: str, lang: str) -> str:
    """Title + brief intro for a chapter (no rule bodies)."""
    title = t(f"reference.colregs.section.{chapter}", lang)
    body = t(f"reference.colregs.intro.{chapter}", lang)
    if body == f"reference.colregs.intro.{chapter}":  # not localised
        return f"<b>{title}</b>"
    return f"<b>{title}</b>\n\n{body}"


def rule_text(rule: str, lang: str) -> str:
    return t(f"reference.colregs.rule.{rule}", lang)


def about_text(lang: str) -> str:
    return t("reference.colregs.about", lang)
