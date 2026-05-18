"""Resolve per-user settings, falling back to env defaults.

Time values are normalised to UTC «HH:MM» so the scheduler can do a flat
string comparison every minute.
"""

from __future__ import annotations

from datetime import datetime

import pytz

from app.config import settings
from app.db.models import User


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
