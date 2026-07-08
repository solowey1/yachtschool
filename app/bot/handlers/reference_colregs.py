"""МППСС-72 reference content builder.

The static structure (chapter → rule numbers) lives in
`app/training/colregs/reference_data.py` so it's importable from keyboards
without pulling in handler code. This module is just the text-rendering
side — it pairs each chapter/rule with its i18n string.
"""

from __future__ import annotations

import re

from app.i18n import t
from app.training.colregs.reference_data import CHAPTER_ORDER, CHAPTER_RULES  # re-export


__all__ = [
    "CHAPTER_ORDER",
    "CHAPTER_RULES",
    "about_text",
    "chapter_intro",
    "chapter_full_text",
    "chapter_rich_html",
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


_LEADING_BOLD = re.compile(r"\s*<b>(.*?)</b>\s*", re.S)


def _blocks_to_html(text: str) -> str:
    """Turn plain paragraph/bullet text into rich-message block HTML.

    Double-newline separates blocks. A block whose lines all start with «•»
    becomes a <ul>; otherwise it's a <p> with single newlines as <br>.
    Inline tags already present in the source (<b>/<i>/<code>) pass through.
    """
    out: list[str] = []
    for block in text.split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if len(lines) > 1 and all(ln.lstrip().startswith("•") for ln in lines):
            items = "".join(f"<li>{ln.lstrip()[1:].strip()}</li>" for ln in lines)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append("<p>" + "<br>".join(lines) + "</p>")
    return "".join(out)


def _labeled_to_rich(text: str, heading_tag: str) -> str:
    """Promote a leading <b>…</b> line to a heading, render the rest as blocks."""
    m = _LEADING_BOLD.match(text)
    if m:
        head = f"<{heading_tag}>{m.group(1)}</{heading_tag}>"
        rest = text[m.end():]
    else:
        head = ""
        rest = text
    return head + _blocks_to_html(rest)


def chapter_rich_html(chapter: str, lang: str) -> str:
    """Whole chapter as Bot API 10.1 rich-message HTML with real headings.

    The chapter title is an <h2>; each rule/annex keeps its own <h3> heading
    (promoted from its leading bold line). No length split — rich messages
    aren't bound by the 4096-char sendMessage limit.
    """
    if chapter == "about":
        return _labeled_to_rich(about_text(lang), "h1")

    parts = [f"<h1>{t(f'reference.colregs.section.{chapter}', lang)}</h1>"]
    intro = t(f"reference.colregs.intro.{chapter}", lang)
    if intro != f"reference.colregs.intro.{chapter}":
        parts.append(f"<p><i>{intro}</i></p>")
    for code in CHAPTER_RULES.get(chapter, []):
        parts.append(_labeled_to_rich(rule_text(code, lang), "h3"))
    return "".join(parts)


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
