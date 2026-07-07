"""COLREGs-72 scenario data.

Defines vessel types, scenario types, and the geometry for generating
random crossing situations. Scenarios are generated procedurally so
the trainer is effectively infinite.

All angle arithmetic uses nautical convention: 0° = North, clockwise.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

SUBJECT_CODE = "colregs"

# ── Vessel types ─────────────────────────────────────────────────────────────

class VesselType(str, Enum):
    SAIL = "sail"
    MOTOR = "motor"
    FISHING = "fishing"       # engaged in fishing — restricted maneuverability
    NUC = "nuc"               # not under command
    RAM = "ram"               # restricted ability to maneuver


VESSEL_LABELS: dict[VesselType, str] = {
    VesselType.SAIL: "парусное",
    VesselType.MOTOR: "моторное",
    VesselType.FISHING: "рыболовное",
    VesselType.NUC: "НУС",
    VesselType.RAM: "СУДОС",
}

# Priority order (Rule 18): higher index = more privileged (give-way is lower)
# NUC > RAM > Fishing > Sail > Motor (when not overtaking/head-on)
PRIORITY: dict[VesselType, int] = {
    VesselType.MOTOR: 0,
    VesselType.SAIL: 1,
    VesselType.FISHING: 2,
    VesselType.RAM: 3,
    VesselType.NUC: 4,
}

# ── Scenario types ────────────────────────────────────────────────────────────

class ScenarioType(str, Enum):
    HEAD_ON = "head_on"
    OVERTAKING = "overtaking"
    CROSSING = "crossing"
    RULE18 = "rule18"          # different vessel type priority


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VesselState:
    """Position and heading of one vessel on the 0..1 unit canvas."""
    x: float          # 0..1
    y: float          # 0..1
    heading: int      # 0..359 nautical degrees
    vtype: VesselType


@dataclass(frozen=True)
class Scenario:
    """A fully specified encounter situation."""
    code: str                  # unique within this generation run; used as entry_code
    scenario_type: ScenarioType
    vessel_a: VesselState
    vessel_b: VesselState
    wind_dir: int              # direction wind is coming FROM, 0..359
    question: str
    correct_answer: str
    wrong_answers: list[str]
    rule_text: str
    description: str           # short label shown in info panel


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _norm(deg: int) -> int:
    return int(deg % 360)


def _place_on_circle(cx: float, cy: float, r: float, bearing: int) -> tuple[float, float]:
    """Place a point at `bearing` (nautical) from centre at radius r."""
    rad = math.radians(bearing)
    return cx + math.sin(rad) * r, cy - math.cos(rad) * r


def _compass_label(deg: int) -> str:
    dirs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
            "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return dirs[round(deg / 22.5) % 16]


def _rel_bearing(observer_hdg: int, target_x: float, target_y: float,
                 obs_x: float, obs_y: float) -> float:
    """Relative bearing of target from observer (0 = dead ahead, 90 = starboard)."""
    abs_bearing = math.degrees(math.atan2(target_x - obs_x, -(target_y - obs_y))) % 360
    return (abs_bearing - observer_hdg) % 360


# ── Scenario generators ───────────────────────────────────────────────────────

def _rand_hdg() -> int:
    return random.randint(0, 359)


# Half-angle of the sailing no-go zone. A sailboat cannot make way when its
# heading is within this many degrees of the wind source — trying to sail
# «into the wind» puts it «in irons». 40° covers typical cruising sailboats
# (racers can point closer, ≈30°, but 40° is a safe general threshold).
SAIL_DEAD_ZONE_HALF = 40


def _sail_angle_off_wind(heading: int, wind: int) -> int:
    """|angle| from the wind source to the bow, folded to [0, 180]. 0 means
    dead into the wind, 180 means running dead downwind.
    """
    rel = (wind - heading) % 360
    return min(rel, 360 - rel)


def _is_sailable(heading: int, wind: int) -> bool:
    return _sail_angle_off_wind(heading, wind) >= SAIL_DEAD_ZONE_HALF


def _rand_sail_hdg(wind: int) -> int:
    """Random heading that keeps a sailboat outside its no-go zone."""
    for _ in range(200):
        hdg = _rand_hdg()
        if _is_sailable(hdg, wind):
            return hdg
    # Deterministically fall back to a broad reach (90° off wind) if
    # 200 rolls somehow all landed in the 80°-wide dead zone.
    return _norm(wind + 90)


def _rand_hdg_for(vtype: VesselType, wind: int) -> int:
    """Random heading appropriate for this vessel type. Sailboats respect
    the dead-zone; everything else can point any way.
    """
    if vtype == VesselType.SAIL:
        return _rand_sail_hdg(wind)
    return _rand_hdg()


def _opposing(hdg: int, spread: int = 10) -> int:
    return _norm(hdg + 180 - spread // 2 + random.randint(0, spread))


def _place_pair_crossing(hdg_a: int, hdg_b: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Place A and B so their headings intersect near canvas centre (0.5, 0.5)."""
    r = 0.28
    ax, ay = _place_on_circle(0.5, 0.5, r, _norm(hdg_a + 180))
    bx, by = _place_on_circle(0.5, 0.5, r, _norm(hdg_b + 180))
    return (ax, ay), (bx, by)


def _gen_head_on(vtype: VesselType) -> Scenario:
    wind = _rand_hdg()
    # Both vessels' headings need to be sailable when vtype=SAIL. Since A and
    # B are ~180° apart, one being close-hauled means the other is running
    # dead-downwind — near the opposite side of the dead zone. Constrain by
    # rejection sampling.
    for _ in range(200):
        hdg_a = _rand_hdg_for(vtype, wind)
        hdg_b = _opposing(hdg_a)
        if vtype != VesselType.SAIL or _is_sailable(hdg_b, wind):
            break
    else:
        hdg_a = _norm(wind + 90)  # beam reach — always valid for both
        hdg_b = _opposing(hdg_a)
    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    label_a = VESSEL_LABELS[vtype]
    return Scenario(
        code=f"head_on_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.HEAD_ON,
        vessel_a=VesselState(ax, ay, hdg_a, vtype),
        vessel_b=VesselState(bx, by, hdg_b, vtype),
        wind_dir=wind,
        description="Встречный курс",
        question="Что обязаны сделать оба судна?",
        correct_answer="Оба изменяют курс вправо, расходятся левыми бортами",
        wrong_answers=[
            "Судно А уступает, Б держит курс",
            "Оба стопорят ход и ждут",
            "Уступает то, кто слева",
        ],
        rule_text=(
            "Правило 14 МППСС: при встречных курсах, когда суда идут прямо "
            "друг на друга или почти прямо, оба должны изменить курс вправо "
            "и разойтись левыми бортами."
        ),
    )


def _gen_overtaking(vtype_a: VesselType, vtype_b: VesselType) -> Scenario:
    wind = _rand_hdg()
    # A overtakes B — A is behind (bearing ~180° from B's stern), similar heading.
    # When either vessel is a sailboat, both headings must sit outside the
    # dead zone; since A ≈ B ± 20°, if B is close-hauled A can be nudged into
    # the no-go, so we rejection-sample.
    for _ in range(200):
        hdg_b = _rand_hdg_for(vtype_b, wind)
        hdg_a = _norm(hdg_b + random.randint(-20, 20))
        a_ok = vtype_a != VesselType.SAIL or _is_sailable(hdg_a, wind)
        b_ok = vtype_b != VesselType.SAIL or _is_sailable(hdg_b, wind)
        if a_ok and b_ok:
            break
    else:
        hdg_b = _norm(wind + 90)
        hdg_a = _norm(hdg_b + random.randint(-20, 20))

    # B ahead of A along the same course
    r = 0.18
    bx, by = _place_on_circle(0.5, 0.5, r, _norm(hdg_b + 180))  # B ahead
    ax, ay = _place_on_circle(0.5, 0.5, r * 2.0, _norm(hdg_a + 180))  # A behind

    label_a = VESSEL_LABELS[vtype_a]
    label_b = VESSEL_LABELS[vtype_b]
    return Scenario(
        code=f"overtaking_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.OVERTAKING,
        vessel_a=VesselState(ax, ay, hdg_a, vtype_a),
        vessel_b=VesselState(bx, by, hdg_b, vtype_b),
        wind_dir=wind,
        description="Обгон",
        question=f"Судно А ({label_a}) обгоняет судно Б ({label_b}). Кто уступает?",
        correct_answer="Судно А — обгоняющее всегда уступает обгоняемому",
        wrong_answers=[
            "Судно Б — оно медленнее",
            f"Зависит от типа: {label_a} vs {label_b}",
            "Оба продолжают курс без изменений",
        ],
        rule_text=(
            "Правило 13 МППСС: обгоняющее судно обязано уступать дорогу "
            "обгоняемому. Это правило действует независимо от типов судов "
            "и отменяет все остальные правила расхождения."
        ),
    )


def _gen_crossing_motor() -> Scenario:
    hdg_a = _rand_hdg()
    angle = random.randint(30, 150)
    if random.random() < 0.5:
        # B is on starboard of A → A gives way
        hdg_b = _norm(hdg_a - angle)
        a_gives_way = True
    else:
        # B is on port of A → B gives way
        hdg_b = _norm(hdg_a + angle)
        a_gives_way = False

    wind = _rand_hdg()
    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    rel_b_from_a = _rel_bearing(hdg_a, bx, by, ax, ay)
    side = "справа" if rel_b_from_a < 180 else "слева"

    if a_gives_way:
        correct = "Судно А уступает — Б у него по правому борту"
        wrong = [
            "Судно Б уступает — А у него по правому борту",
            "Оба продолжают курс",
            "Уступает то, кто идёт быстрее",
        ]
    else:
        correct = "Судно Б уступает — А у него по правому борту"
        wrong = [
            "Судно А уступает — оно пересекает курс Б",
            "Оба изменяют курс вправо",
            "Уступает то, кто идёт быстрее",
        ]

    return Scenario(
        code=f"crossing_motor_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.CROSSING,
        vessel_a=VesselState(ax, ay, hdg_a, VesselType.MOTOR),
        vessel_b=VesselState(bx, by, hdg_b, VesselType.MOTOR),
        wind_dir=wind,
        description="Пересечение курсов (мотор)",
        question=f"Судно Б находится {side} от судна А. Кто уступает дорогу?",
        correct_answer=correct,
        wrong_answers=wrong,
        rule_text=(
            "Правило 15 МППСС: при пересечении курсов судно, у которого "
            "другое судно находится на правом борту, обязано уступить ему "
            "дорогу. Судно, имеющее преимущество, сохраняет курс и скорость."
        ),
    )


def _gen_sail_vs_motor() -> Scenario:
    wind = _rand_hdg()
    hdg_a = _rand_sail_hdg(wind)
    hdg_b = _norm(hdg_a + random.randint(30, 150) * random.choice([-1, 1]))
    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    return Scenario(
        code=f"sail_motor_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.RULE18,
        vessel_a=VesselState(ax, ay, hdg_a, VesselType.SAIL),
        vessel_b=VesselState(bx, by, hdg_b, VesselType.MOTOR),
        wind_dir=wind,
        description="Парусное vs моторное",
        question="Кто обязан уступить дорогу?",
        correct_answer="Судно Б (моторное) уступает судну А (парусному)",
        wrong_answers=[
            "Судно А (парусное) уступает — оно тихоходнее",
            "Тот, у кого другое судно справа",
            "Зависит от ситуации встречи",
        ],
        rule_text=(
            "Правило 18 МППСС: моторное судно, идущее под машиной, "
            "обязано уступать дорогу парусному судну. Исключение: "
            "правило 13 (обгон) и правило 9/10 (узкости/СРД)."
        ),
    )


def _gen_sail_vs_fishing() -> Scenario:
    wind = _rand_hdg()
    hdg_a = _rand_sail_hdg(wind)
    hdg_b = _norm(hdg_a + random.randint(30, 150) * random.choice([-1, 1]))
    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    return Scenario(
        code=f"sail_fishing_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.RULE18,
        vessel_a=VesselState(ax, ay, hdg_a, VesselType.SAIL),
        vessel_b=VesselState(bx, by, hdg_b, VesselType.FISHING),
        wind_dir=wind,
        description="Парусное vs рыболовное",
        question="Кто обязан уступить дорогу?",
        correct_answer="Судно А (парусное) уступает судну Б (рыболовному)",
        wrong_answers=[
            "Судно Б (рыболовное) уступает — парусное экологичнее",
            "Тот, у кого другое судно справа",
            "Оба изменяют курс вправо",
        ],
        rule_text=(
            "Правило 18 МППСС: парусное судно обязано уступать дорогу "
            "судам, занятым ловом рыбы. Суда, занятые ловом рыбы, "
            "ограничены в манёвре и имеют приоритет над парусными."
        ),
    )


def _gen_motor_vs_nuc() -> Scenario:
    hdg_a = _rand_hdg()
    hdg_b = _norm(hdg_a + random.randint(30, 150) * random.choice([-1, 1]))
    wind = _rand_hdg()
    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    return Scenario(
        code=f"motor_nuc_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.RULE18,
        vessel_a=VesselState(ax, ay, hdg_a, VesselType.MOTOR),
        vessel_b=VesselState(bx, by, hdg_b, VesselType.NUC),
        wind_dir=wind,
        description="Моторное vs НУС",
        question="Кто обязан уступить дорогу?",
        correct_answer="Судно А (моторное) уступает судну Б (НУС)",
        wrong_answers=[
            "Судно Б (НУС) уступает — оно мешает движению",
            "Тот, у кого другое судно справа",
            "НУС не участвует в расхождении",
        ],
        rule_text=(
            "Правило 18 МППСС: все суда, кроме судов, лишённых возможности "
            "управляться (НУС), обязаны уступать им дорогу. НУС не может "
            "выполнять требования правил расхождения."
        ),
    )


def _gen_sail_vs_sail() -> Scenario:
    wind = _rand_hdg()
    # Both sailboats must be outside the no-go zone. Rejection-sample until
    # A and B are both sailable (otherwise «правый галс + ветер прямо в нос»
    # comes out physically impossible).
    for _ in range(200):
        hdg_a = _rand_sail_hdg(wind)
        angle = random.randint(30, 150)
        hdg_b = _norm(hdg_a + angle * random.choice([-1, 1]))
        if _is_sailable(hdg_b, wind):
            break
    else:
        hdg_a = _norm(wind + 90)
        hdg_b = _norm(wind - 90)

    (ax, ay), (bx, by) = _place_pair_crossing(hdg_a, hdg_b)

    # Determine tack for each vessel
    # Port tack: wind from port side = wind comes from rel bearing 180..360
    def _port_tack(hdg: int) -> bool:
        rel = (_norm(wind - hdg))
        return rel > 180

    pt_a = _port_tack(hdg_a)
    pt_b = _port_tack(hdg_b)

    tack_a = "левый галс" if pt_a else "правый галс"
    tack_b = "левый галс" if pt_b else "правый галс"

    if pt_a != pt_b:
        # Different tacks: port gives way to starboard
        if pt_a:
            correct = f"Судно А ({tack_a}) уступает судну Б ({tack_b})"
            wrong = [
                f"Судно Б ({tack_b}) уступает судну А ({tack_a})",
                "Тот, у кого другое судно справа по борту",
                "Оба изменяют курс вправо",
            ]
        else:
            correct = f"Судно Б ({tack_b}) уступает судну А ({tack_a})"
            wrong = [
                f"Судно А ({tack_a}) уступает судну Б ({tack_b})",
                "Тот, у кого другое судно справа по борту",
                "Уступает тот, кто идёт медленнее",
            ]
        question = f"А идёт {tack_a}, Б идёт {tack_b}. Кто уступает?"
    else:
        # Same tack: windward gives way to leeward
        # Windward = wind comes from same side as the other vessel
        # Simpler: vessel closer to wind (wind more ahead) is windward
        rel_a = _norm(wind - hdg_a)
        rel_b = _norm(wind - hdg_b)
        # Smaller angle to wind = more windward
        angle_a = rel_a if rel_a <= 180 else 360 - rel_a
        angle_b = rel_b if rel_b <= 180 else 360 - rel_b
        if angle_a < angle_b:
            correct = f"Судно А (с наветра, оба {tack_a}) уступает судну Б"
            wrong = [
                f"Судно Б (с наветра) уступает судну А",
                "Левый галс уступает правому",
                "Оба изменяют курс вправо",
            ]
        else:
            correct = f"Судно Б (с наветра, оба {tack_a}) уступает судну А"
            wrong = [
                f"Судно А (с наветра) уступает судну Б",
                "Левый галс уступает правому",
                "Уступает тот, кто идёт медленнее",
            ]
        question = f"Оба судна идут {tack_a}. Кто уступает?"

    return Scenario(
        code=f"sail_sail_{hdg_a}_{hdg_b}_{wind}",
        scenario_type=ScenarioType.RULE18,
        vessel_a=VesselState(ax, ay, hdg_a, VesselType.SAIL),
        vessel_b=VesselState(bx, by, hdg_b, VesselType.SAIL),
        wind_dir=wind,
        description="Два парусника",
        question=question,
        correct_answer=correct,
        wrong_answers=wrong,
        rule_text=(
            "Правило 12 МППСС: при расхождении двух парусных судов — "
            "идущее левым галсом уступает идущему правым галсом; "
            "при одинаковом галсе — судно с наветра уступает подветренному."
        ),
    )


# ── Public API ────────────────────────────────────────────────────────────────

# Enabled vessel types (can be filtered per user in future)
DEFAULT_ENABLED: list[VesselType] = [
    VesselType.SAIL,
    VesselType.MOTOR,
    VesselType.FISHING,
    VesselType.NUC,
]

# All scenario generators with their relative weights
_GENERATORS = [
    (3, lambda: _gen_head_on(VesselType.MOTOR)),
    (3, lambda: _gen_head_on(VesselType.SAIL)),
    (3, _gen_crossing_motor),
    (3, _gen_sail_vs_motor),
    (2, lambda: _gen_overtaking(VesselType.MOTOR, VesselType.MOTOR)),
    (2, lambda: _gen_overtaking(VesselType.SAIL, VesselType.MOTOR)),
    (2, lambda: _gen_overtaking(VesselType.MOTOR, VesselType.SAIL)),
    (2, _gen_sail_vs_fishing),
    (2, _gen_motor_vs_nuc),
    (2, _gen_sail_vs_sail),
]

_WEIGHTS = [w for w, _ in _GENERATORS]
_FUNCS = [f for _, f in _GENERATORS]


def generate_scenario() -> Scenario:
    """Generate one random scenario."""
    fn = random.choices(_FUNCS, weights=_WEIGHTS, k=1)[0]
    return fn()


# Eight deterministic variants per encounter type → 80 unique scenarios.
# The variant suffix is used as the random seed inside generate_for_code, so
# the same entry_code always yields the same scene. That's what lets the bot
# rebuild a question for explanation/verdict without showing the user a
# different layout from the one they answered.
_TYPE_NAMES: dict[str, Callable[[], Scenario]] = {
    "head_on_motor":   lambda: _gen_head_on(VesselType.MOTOR),
    "head_on_sail":    lambda: _gen_head_on(VesselType.SAIL),
    "crossing_motor":  _gen_crossing_motor,
    "sail_motor":      _gen_sail_vs_motor,
    "overtaking_mm":   lambda: _gen_overtaking(VesselType.MOTOR, VesselType.MOTOR),
    "overtaking_sm":   lambda: _gen_overtaking(VesselType.SAIL, VesselType.MOTOR),
    "overtaking_ms":   lambda: _gen_overtaking(VesselType.MOTOR, VesselType.SAIL),
    "sail_fishing":    _gen_sail_vs_fishing,
    "motor_nuc":       _gen_motor_vs_nuc,
    "sail_sail":       _gen_sail_vs_sail,
}

_VARIANTS_PER_TYPE = 8

SCENARIO_CODES: list[str] = [
    f"colregs_{type_name}_{variant}"
    for type_name in _TYPE_NAMES
    for variant in range(_VARIANTS_PER_TYPE)
]

# Which vessel types appear in each encounter type. The picker filters
# scenarios so that disabling «парусные» in user settings drops every
# scenario where either vessel is sail.
_TYPES_INVOLVED: dict[str, frozenset[VesselType]] = {
    "head_on_motor":   frozenset({VesselType.MOTOR}),
    "head_on_sail":    frozenset({VesselType.SAIL}),
    "crossing_motor":  frozenset({VesselType.MOTOR}),
    "sail_motor":      frozenset({VesselType.SAIL, VesselType.MOTOR}),
    "overtaking_mm":   frozenset({VesselType.MOTOR}),
    "overtaking_sm":   frozenset({VesselType.SAIL, VesselType.MOTOR}),
    "overtaking_ms":   frozenset({VesselType.SAIL, VesselType.MOTOR}),
    "sail_fishing":    frozenset({VesselType.SAIL, VesselType.FISHING}),
    "motor_nuc":       frozenset({VesselType.MOTOR, VesselType.NUC}),
    "sail_sail":       frozenset({VesselType.SAIL}),
}


def involved_types(entry_code: str) -> frozenset[VesselType]:
    """Vessel types that appear in the scenario identified by `entry_code`."""
    return _TYPES_INVOLVED.get(_type_of(entry_code), frozenset())


def _type_of(entry_code: str) -> str:
    """Strip the `colregs_` prefix and trailing `_<variant>` to get the encounter type."""
    if not entry_code.startswith("colregs_"):
        raise KeyError(f"unknown colregs entry_code: {entry_code!r}")
    body = entry_code[len("colregs_"):]
    # variant index is always the last underscore-separated token
    head, _, _tail = body.rpartition("_")
    return head if head in _TYPE_NAMES else body


def generate_for_code(entry_code: str) -> Scenario:
    """Build the scenario identified by `entry_code` — same code → same scene.

    Saves/restores the global random state so seeding here doesn't perturb
    other randomness in the same process (e.g. quiz option shuffles in
    other trainers).
    """
    type_name = _type_of(entry_code)
    fn = _TYPE_NAMES.get(type_name)
    if fn is None:
        raise KeyError(f"unknown colregs entry_code: {entry_code!r}")

    state = random.getstate()
    random.seed(entry_code)
    try:
        scenario = fn()
    finally:
        random.setstate(state)
    # The generators baked their own random `code` into the Scenario; replace
    # it with the canonical entry_code so caller sees what it asked for.
    return Scenario(
        code=entry_code,
        scenario_type=scenario.scenario_type,
        vessel_a=scenario.vessel_a,
        vessel_b=scenario.vessel_b,
        wind_dir=scenario.wind_dir,
        description=scenario.description,
        question=scenario.question,
        correct_answer=scenario.correct_answer,
        wrong_answers=scenario.wrong_answers,
        rule_text=scenario.rule_text,
    )
