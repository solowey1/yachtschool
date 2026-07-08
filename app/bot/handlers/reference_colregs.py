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
    "chapter_full_text",
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
    """Annex codes (a1..a4) are stored under a separate i18n branch."""
    if rule.startswith("a"):
        return t(f"reference.colregs.annex.{rule}", lang)
    return t(f"reference.colregs.rule.{rule}", lang)


def about_text(lang: str) -> str:
    return t("reference.colregs.about", lang)


def chapter_full_text(chapter: str, lang: str) -> str:
    """Whole chapter as one long HTML string: the intro heading followed by
    every rule (or annex) in full. The caller splits it into ≤4096-char
    messages on paragraph boundaries — no per-rule pagination.
    """
    if chapter == "about":
        return about_text(lang)
    parts = [chapter_intro(chapter, lang)]
    for code in CHAPTER_RULES.get(chapter, []):
        parts.append(rule_text(code, lang))
    return "\n\n".join(parts)
