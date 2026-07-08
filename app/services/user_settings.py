"""Resolve per-user settings, falling back to env defaults.

Time values are normalised to UTC «HH:MM» so the scheduler can do a flat
string comparison every minute.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from app.config import settings
from app.db.models import User

# Preset pause durations offered in the picker (days). `0` is treated as
# «forever» by set_pause().
PAUSE_PRESETS: tuple[int, ...] = (1, 3, 7, 14, 30)
_PAUSE_FOREVER = datetime(9999, 12, 31, tzinfo=pytz.UTC)


def env_default_time_utc() -> str:
    """Convert the env-configured default time (in env's timezone) → UTC «HH:MM»."""
    tz = pytz.timezone(settings.daily_delivery_timezone)
    today = datetime.now(tz).date()
    local = tz.localize(
        datetime(
            today.year,
            today.month,
            today.day,
            settings.daily_delivery_hour,
            settings.daily_delivery_minute,
        )
    )
    return local.astimezone(pytz.UTC).strftime("%H:%M")


def env_default_time_str() -> str:
    """Default time formatted as «HH:MM» in env's timezone — for display."""
    return f"{settings.daily_delivery_hour:02d}:{settings.daily_delivery_minute:02d}"


def env_default_timezone() -> str:
    return settings.daily_delivery_timezone


def env_default_count() -> int:
    return settings.daily_questions_count


def env_default_language() -> str:
    return settings.default_language


def effective_time_utc(user: User) -> str:
    """The UTC «HH:MM» when this user should receive their daily batch."""
    return user.delivery_time_utc or env_default_time_utc()


def effective_count(user: User) -> int:
    return user.daily_questions_count or env_default_count()


def effective_language(user: User) -> str:
    return user.language or env_default_language()


def is_time_overridden(user: User) -> bool:
    return user.delivery_time_utc is not None


def is_count_overridden(user: User) -> bool:
    return user.daily_questions_count is not None


# ── COLREGs-specific settings ────────────────────────────────────────────────

_COLREGS_ALL_TYPES: tuple[str, ...] = ("sail", "motor", "fishing", "nuc", "ram")


def colregs_enabled_types(user: User) -> set[str]:
    """Parse the stored CSV into a set; empty/invalid defaults to all types."""
    raw = (user.colregs_enabled_types or "").strip()
    if not raw:
        return set(_COLREGS_ALL_TYPES)
    picked = {t.strip() for t in raw.split(",") if t.strip()}
    valid = picked & set(_COLREGS_ALL_TYPES)
    return valid or set(_COLREGS_ALL_TYPES)


def colregs_all_types() -> tuple[str, ...]:
    return _COLREGS_ALL_TYPES


def colregs_set_enabled_types(user: User, types: set[str]) -> None:
    """Persist; refuses to leave the user with zero types (would be unrunnable)."""
    safe = (types & set(_COLREGS_ALL_TYPES)) or set(_COLREGS_ALL_TYPES)
    # Stable order — keep the canonical ordering in DB for readability.
    user.colregs_enabled_types = ",".join(t for t in _COLREGS_ALL_TYPES if t in safe)


def colregs_toggle_type(user: User, vessel_type: str) -> None:
    """Flip a vessel type on/off. Refuses to disable the last enabled one."""
    cur = colregs_enabled_types(user)
    if vessel_type in cur and len(cur) > 1:
        cur.discard(vessel_type)
    else:
        cur.add(vessel_type)
    colregs_set_enabled_types(user, cur)


def colregs_night_mode(user: User) -> bool:
    return bool(user.colregs_night_mode)


def colregs_set_night_mode(user: User, value: bool) -> None:
    user.colregs_night_mode = value


# ── Daily-delivery pause ─────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(pytz.UTC)


def _ensure_aware(dt: datetime) -> datetime:
    """DB may hand back a naive datetime under some drivers — coerce to UTC."""
    return dt if dt.tzinfo is not None else pytz.UTC.localize(dt)


def is_paused(user: User, now: datetime | None = None) -> bool:
    if user.paused_until is None:
        return False
    return _ensure_aware(user.paused_until) > (now or _now_utc())


def is_paused_forever(user: User) -> bool:
    return user.paused_until is not None and _ensure_aware(user.paused_until).year >= 9000


def pause_ends_at(user: User) -> datetime | None:
    """When the pause naturally lifts. None if not paused or paused forever."""
    if not is_paused(user) or is_paused_forever(user):
        return None
    return _ensure_aware(user.paused_until) if user.paused_until else None


def set_pause(user: User, days: int) -> None:
    """`days > 0` → pause for that many days. `days == 0` → pause forever."""
    if days <= 0:
        user.paused_until = _PAUSE_FOREVER
    else:
        user.paused_until = _now_utc() + timedelta(days=days)


def unpause(user: User) -> None:
    user.paused_until = None
