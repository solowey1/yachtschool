"""МППСС-72 reference content + chapter navigation.

The text of all 41 COLREGs rules is held in i18n under
`reference.colregs.rule.<N>` (where N is 1..41 zero-padded to 2 digits).
A small Python map links chapters/sections to the ranges of rule numbers
they contain — that's enough to render both the chapter list and the
per-chapter rule buttons without hard-coding navigation in handlers.
"""

from __future__ import annotations

from app.i18n import t

# Chapter → ordered list of rule numbers (as 2-digit strings) that belong to it.
CHAPTER_RULES: dict[str, list[str]] = {
    "part_a":     [f"{n:02d}" for n in range(1, 4)],     # 1..3
    "part_b_i":   [f"{n:02d}" for n in range(4, 11)],    # 4..10
    "part_b_ii":  [f"{n:02d}" for n in range(11, 19)],   # 11..18
    "part_b_iii": ["19"],
    "part_c":     [f"{n:02d}" for n in range(20, 32)],   # 20..31
    "part_d":     [f"{n:02d}" for n in range(32, 38)],   # 32..37
    "part_e":     ["38"],
}

# Ordered chapters for the top-level list — drives the keyboard layout.
CHAPTER_ORDER: tuple[str, ...] = (
    "about",
    "part_a",
    "part_b_i",
    "part_b_ii",
    "part_b_iii",
    "part_c",
    "part_d",
    "part_e",
)


def chapter_intro(chapter: str, lang: str) -> str:
    """Title + brief intro text for one chapter (no rule bodies)."""
    title = t(f"reference.colregs.section.{chapter}", lang)
    body = t(f"reference.colregs.intro.{chapter}", lang)
    if body == f"reference.colregs.intro.{chapter}":  # not localised
        return f"<b>{title}</b>"
    return f"<b>{title}</b>\n\n{body}"


def rule_text(rule: str, lang: str) -> str:
    """Full text of one rule (e.g. «14» → Rule 14 head-on)."""
    return t(f"reference.colregs.rule.{rule}", lang)


def about_text(lang: str) -> str:
    return t("reference.colregs.about", lang)
