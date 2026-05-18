"""Match an inline-query string to МСС flag/pennant codes.

Empty query → everything, in canonical display order (letters, then digits,
then substitutes, then answering pennant).

Non-empty query is matched against:
    * the code itself (single letter or digit, ignoring case)
    * the Russian name (Альфа, Браво, …, 1-й заменяющий, Ответный, …)
    * the English NATO/МСС phonetic (Alpha, Bravo, …, Nadazero, …)
    * the single-letter signal meaning (so «помощь» finds V)
"""

from __future__ import annotations

from app.i18n import t
from app.training.mcs65 import data, pennants


def all_codes() -> list[str]:
    """Canonical display order across letters + numerals + substitutes + answering."""
    return [
        *data.all_codes(),
        *pennants.numeral_codes(),
        "S1",
        "S2",
        "S3",
        "AP",
    ]


def _matches(code: str, q: str, lang: str) -> bool:
    """True if `q` (lowercased) appears in any searchable field for `code`."""
    if code.lower() == q or code.lower().startswith(q):
        return True

    # Letter entries
    if len(code) == 1 and code.isalpha():
        ru_name = t(f"mcs65.name.{code}", lang).lower()
        en_name = data.NATO_PHONETIC_EN.get(code, "").lower()
        meaning = t(f"mcs65.meaning.{code}", lang).lower()
        return q in ru_name or q in en_name or q in meaning

    # Numeral pennants — also match the bare digit.
    if code.startswith("N"):
        digit = code[1:]
        if q == digit:
            return True
        ru_name = t(f"mcs65.pennant_name.{code}", lang).lower()
        en_name = pennants.PHONETIC_EN.get(code, "").lower()
        return q in ru_name or q in en_name or q in digit

    # Substitutes / answering pennant
    ru_name = t(f"mcs65.pennant_name.{code}", lang).lower()
    ru_label = t(f"mcs65.pennant_label.{code}", lang).lower()
    en_name = pennants.PHONETIC_EN.get(code, "").lower()
    return q in ru_name or q in ru_label or q in en_name


def search(query: str, lang: str) -> list[str]:
    q = query.strip().lower()
    if not q:
        return all_codes()

    # Single-character queries are exact lookups — otherwise a bare "b" would
    # also drag in November/Bissotwo/substitutes (all contain «b»).
    if len(q) == 1:
        if q.isalpha():
            code = q.upper()
            return [code] if code in data.all_codes() else []
        if q.isdigit():
            code = f"N{q}"
            return [code] if code in pennants.numeral_codes() else []
        return []

    return [c for c in all_codes() if _matches(c, q, lang)]
