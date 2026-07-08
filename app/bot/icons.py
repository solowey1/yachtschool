"""Custom-emoji icon IDs for inline-keyboard buttons.

Telegram's `InlineKeyboardButton.icon_custom_emoji_id` (Bot API ≥ 9.x,
aiogram ≥ 3.29) renders a custom emoji as the button's leading icon. We
keep the IDs here rather than scattered across keyboard builders so the
whole icon set is swappable in one place.

The emoji must belong to a pack the bot can use; the IDs below are the
ones provisioned for this bot. An unavailable ID makes Telegram reject
the whole keyboard, so treat this file as the single source of truth.
"""

from __future__ import annotations

# ── Main menu ────────────────────────────────────────────────────────────────
MENU_REFERENCE = "5778672437122045013"
MENU_TRAINING = "5938195768832692153"
MENU_STATS = "5936143551854285132"
MENU_SETTINGS = "5850309953293653168"
MENU_DONATE = "5773677501825945508"

# ── Shared navigation ────────────────────────────────────────────────────────
BACK = "5960671702059848143"        # «Назад»
TO_MAIN = "5938537205847822613"     # «В главное меню»

# ── Donate ───────────────────────────────────────────────────────────────────
DONATE_STAR = "6028338546736107668"  # every Stars-amount button

# ── Statistics ───────────────────────────────────────────────────────────────
STATS_DETAILED_LOCKED = "5776227595708273495"    # «Подробная статистика» — not bought
STATS_DETAILED_UNLOCKED = "5935913431801532272"  # «Подробная статистика» — bought
STATS_BUY = "6028338546736107668"                # «Оплатить» button

# ── Settings rows ────────────────────────────────────────────────────────────
SETTINGS_TIME = "5983150113483134607"
SETTINGS_PAUSE = "6039636621416993073"

# ── Training: МППСС-72 submenu ───────────────────────────────────────────────
COLREGS_TRAIN = "5773626993010546707"       # «Тренировать»
COLREGS_TRAIN_SETTINGS = "6037496202990194718"  # «Настройки тренажёра»

# ── Training: МСС-65 «Буквы (смешанный режим)» ───────────────────────────────
MCS65_LETTERS = "5767262289564536912"

# ── Reference: МСС-65 section list ───────────────────────────────────────────
# Keys match the section codes in keyboards.MCS65_REFERENCE_SECTIONS.
MCS65_SECTION: dict[str, str] = {
    "about": "6028435952299413210",
    "flags": "6041923781696426657",
    "names": "6030474781864759622",
    "pennants": "5794164805065514131",
    "substitutes": "6030657343744644592",
    "signals": "6021618194228187816",
    "morse": "5766994197705921104",
}

# ── Digit icons 1..10 ────────────────────────────────────────────────────────
# Used to show the current daily-question count and to label the count picker.
# The trainer only offers 1/3/5/7/10, but the full set is kept for future
# presets.
DIGIT: dict[int, str] = {
    1: "5794164805065514131",
    2: "5794085322400733645",
    3: "5794280000383358988",
    4: "5794241397217304511",
    5: "5793985348446984682",
    6: "5794324702402976226",
    7: "5793942849745591465",
    8: "5793926687783655907",
    9: "5793979472931723221",
    10: "5794375786743995258",
}


def digit_icon(n: int) -> str | None:
    return DIGIT.get(int(n))
