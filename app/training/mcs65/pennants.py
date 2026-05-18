"""Non-letter МСС-65 flags: numeral pennants (0–9), three substitutes, answering pennant.

Phonetic names follow the 1965 edition of the Code (Nadazero, Unaone, …, Novenine).
Renderer lives in `pennant_renderer.py`; per-entry text strings (names, meanings)
live in i18n under `mcs65.pennant_name.*` / `mcs65.pennant_meaning.*`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PennantKind(str, Enum):
    NUMERAL = "numeral"
    SUBSTITUTE = "substitute"
    ANSWERING = "answering"


@dataclass(frozen=True)
class PennantEntry:
    code: str  # globally-unique within the MCS pennant set (e.g. "N0", "S1", "AP")
    kind: PennantKind
    short_label: str  # button-friendly label, e.g. "0", "1-й зам.", "Ответный"
    morse: str | None = None  # numeric Morse codes; None for substitutes / answering


NUMERAL_ENTRIES: tuple[PennantEntry, ...] = (
    PennantEntry("N0", PennantKind.NUMERAL, "0", "-----"),
    PennantEntry("N1", PennantKind.NUMERAL, "1", ".----"),
    PennantEntry("N2", PennantKind.NUMERAL, "2", "..---"),
    PennantEntry("N3", PennantKind.NUMERAL, "3", "...--"),
    PennantEntry("N4", PennantKind.NUMERAL, "4", "....-"),
    PennantEntry("N5", PennantKind.NUMERAL, "5", "....."),
    PennantEntry("N6", PennantKind.NUMERAL, "6", "-...."),
    PennantEntry("N7", PennantKind.NUMERAL, "7", "--..."),
    PennantEntry("N8", PennantKind.NUMERAL, "8", "---.."),
    PennantEntry("N9", PennantKind.NUMERAL, "9", "----."),
)

SUBSTITUTE_ENTRIES: tuple[PennantEntry, ...] = (
    PennantEntry("S1", PennantKind.SUBSTITUTE, "1-й зам."),
    PennantEntry("S2", PennantKind.SUBSTITUTE, "2-й зам."),
    PennantEntry("S3", PennantKind.SUBSTITUTE, "3-й зам."),
)

ANSWERING_ENTRY = PennantEntry("AP", PennantKind.ANSWERING, "Ответный")

ALL_ENTRIES: tuple[PennantEntry, ...] = (*NUMERAL_ENTRIES, *SUBSTITUTE_ENTRIES, ANSWERING_ENTRY)
ENTRIES_BY_CODE: dict[str, PennantEntry] = {e.code: e for e in ALL_ENTRIES}

# English names — same purpose as NATO_PHONETIC_EN in data.py: cross-language
# inline search. МСС-65 numeric phonetics (Nadazero/Unaone/…) + idiomatic names
# for the substitute and answering pennants.
PHONETIC_EN: dict[str, str] = {
    "N0": "Nadazero", "N1": "Unaone", "N2": "Bissotwo", "N3": "Terrathree",
    "N4": "Kartefour", "N5": "Pantafive", "N6": "Soxisix", "N7": "Setteseven",
    "N8": "Oktoeight", "N9": "Novenine",
    "S1": "First substitute", "S2": "Second substitute", "S3": "Third substitute",
    "AP": "Answering pennant",
}


def all_codes() -> list[str]:
    return [e.code for e in ALL_ENTRIES]


def numeral_codes() -> list[str]:
    return [e.code for e in NUMERAL_ENTRIES]


def get(code: str) -> PennantEntry:
    return ENTRIES_BY_CODE[code]
