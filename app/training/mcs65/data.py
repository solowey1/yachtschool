"""МСС-65 reference data — letters A–Z with Morse codes.

Russian names and single-letter signal meanings live in i18n
(see app/i18n/locales/ru.json under "mcs65.name" / "mcs65.meaning").
"""

from __future__ import annotations

from dataclasses import dataclass

SUBJECT_CODE = "mcs65"


@dataclass(frozen=True)
class SignalEntry:
    code: str  # 'A'..'Z' — the letter and identifier
    morse: str  # e.g. '.-'


ENTRIES: tuple[SignalEntry, ...] = (
    SignalEntry("A", ".-"),
    SignalEntry("B", "-..."),
    SignalEntry("C", "-.-."),
    SignalEntry("D", "-.."),
    SignalEntry("E", "."),
    SignalEntry("F", "..-."),
    SignalEntry("G", "--."),
    SignalEntry("H", "...."),
    SignalEntry("I", ".."),
    SignalEntry("J", ".---"),
    SignalEntry("K", "-.-"),
    SignalEntry("L", ".-.."),
    SignalEntry("M", "--"),
    SignalEntry("N", "-."),
    SignalEntry("O", "---"),
    SignalEntry("P", ".--."),
    SignalEntry("Q", "--.-"),
    SignalEntry("R", ".-."),
    SignalEntry("S", "..."),
    SignalEntry("T", "-"),
    SignalEntry("U", "..-"),
    SignalEntry("V", "...-"),
    SignalEntry("W", ".--"),
    SignalEntry("X", "-..-"),
    SignalEntry("Y", "-.--"),
    SignalEntry("Z", "--.."),
)

ENTRIES_BY_CODE: dict[str, SignalEntry] = {e.code: e for e in ENTRIES}

# NATO phonetic names in English — used by the inline-search matcher so users
# can type «bravo» as easily as «браво». Stored in code (not i18n) because
# these are an international standard, not a translation.
NATO_PHONETIC_EN: dict[str, str] = {
    "A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta", "E": "Echo",
    "F": "Foxtrot", "G": "Golf", "H": "Hotel", "I": "India", "J": "Juliet",
    "K": "Kilo", "L": "Lima", "M": "Mike", "N": "November", "O": "Oscar",
    "P": "Papa", "Q": "Quebec", "R": "Romeo", "S": "Sierra", "T": "Tango",
    "U": "Uniform", "V": "Victor", "W": "Whiskey", "X": "X-ray", "Y": "Yankee",
    "Z": "Zulu",
}


def all_codes() -> list[str]:
    return [e.code for e in ENTRIES]


def get(code: str) -> SignalEntry:
    return ENTRIES_BY_CODE[code]
