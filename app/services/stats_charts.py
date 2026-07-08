"""Text-based accuracy charts and period math for the statistics screens.

Charts are drawn with mahjong-tile block characters so they render
identically on every client without images:
    🀫 filled cell = 10 % of accuracy, 🀆 empty cell = the remainder.

All period math is done in UTC (answers are stored as timestamptz; the
daily scheduler already works in UTC), so «today»/«this week»/«this month»
are UTC-aligned.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytz

FILLED = "🀫"
EMPTY = "🀆"
_CELLS = 10


def bar(pct: float) -> str:
    """A 10-cell bar for a 0..100 percentage."""
    filled = round(pct / 100 * _CELLS)
    filled = max(0, min(_CELLS, filled))
    return FILLED * filled + EMPTY * (_CELLS - filled)


def pct(correct: int, total: int) -> int:
    return round(correct * 100 / total) if total else 0


def chart_row(label: str, correct: int, total: int, *, width: int = 0) -> str:
    """`label 🀫🀫…🀆 NN%` — one accuracy line, wrapped in monospace so the
    labels line up under one another. `width` left-pads the label so rows
    with different-length labels still align. «—» when there's no data.
    """
    lbl = label.ljust(width) if width else label
    if total == 0:
        body = f"{lbl}  {EMPTY * _CELLS}  —"
    else:
        body = f"{lbl}  {bar(pct(correct, total))}  {pct(correct, total)}% ({correct}/{total})"
    return f"<code>{body}</code>"


# ── Period math (UTC) ─────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(pytz.UTC)


def _midnight(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime
    label: str


def day_period(offset: int, *, ref: datetime | None = None) -> Period:
    ref = ref or now_utc()
    start = _midnight(ref) + timedelta(days=offset)
    end = start + timedelta(days=1)
    return Period(start, end, start.strftime("%d.%m"))


def week_period(offset: int, *, ref: datetime | None = None) -> Period:
    ref = ref or now_utc()
    monday = _midnight(ref) - timedelta(days=ref.weekday())
    start = monday + timedelta(weeks=offset)
    end = start + timedelta(days=7)
    last = end - timedelta(days=1)
    return Period(start, end, f"{start.strftime('%d.%m')}–{last.strftime('%d.%m')}")


def _add_months(d: datetime, months: int) -> datetime:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    return d.replace(year=year, month=month, day=1)


_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
_MONTHS_RU_NOM = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def month_period(offset: int, *, ref: datetime | None = None) -> Period:
    ref = ref or now_utc()
    start = _add_months(_midnight(ref).replace(day=1), offset)
    end = _add_months(start, 1)
    return Period(start, end, f"{_MONTHS_RU_NOM[start.month - 1]} {start.year}")


def last_weeks(count: int, *, ref: datetime | None = None) -> list[Period]:
    """The `count` most recent whole weeks, oldest first (for the 4-week chart)."""
    return [week_period(-i, ref=ref) for i in range(count - 1, -1, -1)]


def period_for(unit: str, offset: int) -> Period:
    return {"day": day_period, "week": week_period, "month": month_period}[unit](offset)
