from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings  # noqa: F401  — used inside Translator methods

_LOCALES_DIR = Path(__file__).parent / "locales"


class Translator:
    """Loads JSON locales and resolves dotted keys.

    Locales live in app/i18n/locales/<lang>.json. Keys are dot-paths
    (e.g. "menu.title"). Values support {placeholder} interpolation.
    Missing translations fall back to the default language; if still
    missing, the key itself is returned.
    """

    def __init__(self, default_lang: str | None = None) -> None:
        self.default_lang = default_lang or settings.default_language
        self._data: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not _LOCALES_DIR.exists():
            return
        for f in _LOCALES_DIR.glob("*.json"):
            with f.open(encoding="utf-8") as fp:
                self._data[f.stem] = json.load(fp)

    def available_languages(self) -> list[str]:
        return sorted(self._data.keys())

    def _resolve_raw(self, lang: str, key: str) -> Any:
        cursor: Any = self._data.get(lang)
        if cursor is None:
            return None
        for part in key.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                return None
            cursor = cursor[part]
        return cursor

    def _resolve(self, lang: str, key: str) -> str | None:
        value = self._resolve_raw(lang, key)
        return value if isinstance(value, str) else None

    def t(self, key: str, lang: str | None = None, /, **kwargs: Any) -> str:
        lang = lang or self.default_lang
        value = self._resolve(lang, key)
        if value is None and lang != self.default_lang:
            value = self._resolve(self.default_lang, key)
        if value is None:
            return key
        # `bot_username` is always available without explicit kwarg — saves
        # passing it through every t() call in handlers.
        kwargs.setdefault("bot_username", settings.bot_username)
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value

    def t_list(self, key: str, lang: str | None = None) -> list[str]:
        """Read a list value from i18n (e.g. distractor pools).

        Returns [] when missing or not a list. Falls back to the default language
        before giving up, same as `t`.
        """
        lang = lang or self.default_lang
        value = self._resolve_raw(lang, key)
        if not isinstance(value, list) and lang != self.default_lang:
            value = self._resolve_raw(self.default_lang, key)
        if not isinstance(value, list):
            return []
        return [str(v) for v in value]


_translator: Translator | None = None


def translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def t(key: str, lang: str | None = None, /, **kwargs: Any) -> str:
    return translator().t(key, lang, **kwargs)


def t_list(key: str, lang: str | None = None) -> list[str]:
    return translator().t_list(key, lang)
