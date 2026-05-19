"""МППСС-72 reference-page data — chapter → rule-number ranges.

Kept in `app/training/colregs/` rather than `app/bot/handlers/` so that
keyboards (which are pulled in transitively from quiz_engine) don't have
to import a handler module, which would close a circular dependency.
"""

from __future__ import annotations

# Chapter → ordered list of rule numbers (2-digit strings).
CHAPTER_RULES: dict[str, list[str]] = {
    "part_a":     [f"{n:02d}" for n in range(1, 4)],     # 1..3
    "part_b_i":   [f"{n:02d}" for n in range(4, 11)],    # 4..10
    "part_b_ii":  [f"{n:02d}" for n in range(11, 19)],   # 11..18
    "part_b_iii": ["19"],
    "part_c":     [f"{n:02d}" for n in range(20, 32)],   # 20..31
    "part_d":     [f"{n:02d}" for n in range(32, 38)],   # 32..37
    "part_e":     ["38"],
}

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
