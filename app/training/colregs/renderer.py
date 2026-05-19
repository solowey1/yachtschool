"""Renders COLREGs encounter scenarios to PNG using Pillow.

Two visual modes:
  • `day`   — daylight scene with hull silhouettes, course-projection
    dashes, А/Б letters drawn inside each hull, compass, bottom legend.
  • `night` — dark scene with only the vessels' navigation lights
    visible at the correct positions for the vessel's heading and type
    (Rules 23/25/26/27/30). No hull, no course line — the student has
    to read off type and direction from the light arrangement alone.

In both modes a single wind arrow originates at the compass centre and
points toward the side wind is coming from; the bottom legend strip
shows А / Б chips with vessel type and heading.
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

from app.training.colregs.data import Scenario, VESSEL_LABELS, VesselType, _compass_label

# ── Canvas constants ──────────────────────────────────────────────────────────

W = H = 600
CX = CY = 300
COMPASS_R = 230
VESSEL_SIZE = 28
COURSE_LINE_LEN = 70
LEGEND_HEIGHT = 56

# ── Palettes ─────────────────────────────────────────────────────────────────

# Day palette
DAY = {
    "bg": (216, 236, 250),
    "grid": (200, 224, 240),
    "compass_ring": (110, 145, 195),
    "compass_text": (50, 90, 150),
    "wind": (28, 145, 70),
    "legend_bg": (245, 250, 254),
    "frame": (140, 165, 200),
    "letter_a": (28, 70, 175),
    "letter_b": (175, 50, 30),
    "label_text": (60, 60, 60),
}

# Night palette
NIGHT = {
    "bg": (12, 18, 38),
    "grid": (28, 38, 64),
    "compass_ring": (60, 90, 140),
    "compass_text": (140, 180, 230),
    "wind": (90, 200, 140),
    "legend_bg": (28, 38, 64),
    "frame": (60, 90, 140),
    "letter_a": (180, 210, 255),
    "letter_b": (255, 210, 200),
    "label_text": (210, 220, 240),
}

VESSEL_COLORS: dict[VesselType, tuple[int, int, int]] = {
    VesselType.MOTOR:   (200, 80, 40),
    VesselType.SAIL:    (40, 110, 200),
    VesselType.FISHING: (40, 150, 70),
    VesselType.NUC:     (155, 50, 155),
    VesselType.RAM:     (200, 150, 30),
}

VESSEL_DARK: dict[VesselType, tuple[int, int, int]] = {
    VesselType.MOTOR:   (130, 50, 20),
    VesselType.SAIL:    (20, 65, 140),
    VesselType.FISHING: (20, 95, 35),
    VesselType.NUC:     (95, 20, 95),
    VesselType.RAM:     (130, 95, 15),
}

WHITE = (255, 255, 255)
BLACK = (10, 10, 10)

# Navigation-light colours (per Rule 21).
LIGHT_WHITE  = (255, 255, 240)
LIGHT_RED    = (255, 70, 70)
LIGHT_GREEN  = (70, 255, 110)
LIGHT_YELLOW = (255, 220, 80)

# Brightness factors used to distinguish А (lighter) from Б (darker) when
# both vessels are of the same type — otherwise they'd be indistinguishable
# in the day-mode rendering. Applied to hull fill in day mode; applied to
# the glow alpha in night mode (so A's lights look slightly brighter).
A_TINT = 1.28
B_TINT = 0.72


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]

# ── Font helpers ──────────────────────────────────────────────────────────────

_BOLD_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
_REGULAR_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in _BOLD_PATHS if bold else _REGULAR_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _to_canvas(x: float, y: float) -> tuple[float, float]:
    margin = 50
    usable_h = H - LEGEND_HEIGHT - margin
    size = W - 2 * margin
    return margin + x * size, margin + y * usable_h


def _text_centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
                   font: ImageFont.FreeTypeFont, fill: tuple[int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((xy[0] - tw // 2 - bbox[0], xy[1] - th // 2 - bbox[1]),
              text, fill=fill, font=font)


def _heading_vectors(heading_deg: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return (forward, starboard) unit vectors for a vessel at this heading."""
    rad = math.radians(heading_deg)
    fwd = (math.sin(rad), -math.cos(rad))
    stb = (math.cos(rad), math.sin(rad))
    return fwd, stb


# ── Background / compass / legend (mode-aware) ────────────────────────────────

def _draw_background(draw: ImageDraw.ImageDraw, pal: dict) -> None:
    draw.rectangle([(0, 0), (W, H)], fill=pal["bg"])
    for i in range(0, W + 1, 60):
        draw.line([(i, 0), (i, H - LEGEND_HEIGHT)], fill=pal["grid"], width=1)
    for i in range(0, H - LEGEND_HEIGHT + 1, 60):
        draw.line([(0, i), (W, i)], fill=pal["grid"], width=1)


def _draw_compass(draw: ImageDraw.ImageDraw, pal: dict) -> None:
    cy = CY - LEGEND_HEIGHT // 2
    draw.ellipse(
        [(CX - COMPASS_R, cy - COMPASS_R), (CX + COMPASS_R, cy + COMPASS_R)],
        outline=pal["compass_ring"], width=1,
    )
    draw.ellipse([(CX - 3, cy - 3), (CX + 3, cy + 3)], fill=pal["compass_ring"])
    for deg in range(0, 360, 22):
        rad = math.radians(deg)
        is_card = deg % 90 == 0
        is_inter = deg % 45 == 0 and not is_card
        inset = 10 if is_card else (6 if is_inter else 3)
        sin_d, cos_d = math.sin(rad), -math.cos(rad)
        ix = CX + sin_d * (COMPASS_R - inset)
        iy = cy + cos_d * (COMPASS_R - inset)
        ox = CX + sin_d * COMPASS_R
        oy = cy + cos_d * COMPASS_R
        draw.line([(ix, iy), (ox, oy)], fill=pal["compass_ring"], width=2 if is_card else 1)

    main_f = _font(17)
    small_f = _font(11)
    for deg, label in {0: "С", 90: "В", 180: "Ю", 270: "З"}.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 18)
        ly = cy - math.cos(rad) * (COMPASS_R + 18)
        _text_centered(draw, (lx, ly), label, main_f, pal["compass_text"])
    for deg, label in {45: "СВ", 135: "ЮВ", 225: "ЮЗ", 315: "СЗ"}.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 16)
        ly = cy - math.cos(rad) * (COMPASS_R + 16)
        _text_centered(draw, (lx, ly), label, small_f, pal["compass_text"])


def _draw_wind(draw: ImageDraw.ImageDraw, pal: dict, wind_dir: int) -> None:
    """Short arrow from compass centre pointing toward the side wind comes FROM.

    Mariner convention: wind_dir = direction wind is coming from. The head
    lands ~100 px from centre (half the compass radius), so the arrow is
    compact rather than crossing the whole rose. Label goes outside the head.
    """
    cy = CY - LEGEND_HEIGHT // 2
    rad = math.radians(wind_dir)
    inner_r = 8
    outer_r = inner_r + 90  # was ~196 px → halved
    sx = CX + math.sin(rad) * inner_r
    sy = cy - math.cos(rad) * inner_r
    ex = CX + math.sin(rad) * outer_r
    ey = cy - math.cos(rad) * outer_r
    draw.line([(sx, sy), (ex, ey)], fill=pal["wind"], width=4)

    dx, dy = ex - sx, ey - sy
    length = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    base_x, base_y = ex - ux * 12, ey - uy * 12
    half = 7
    p1 = (base_x - uy * half, base_y + ux * half)
    p2 = (base_x + uy * half, base_y - ux * half)
    draw.polygon([(ex, ey), p1, p2], fill=pal["wind"])

    label = f"ветер {_compass_label(wind_dir)} ({wind_dir}°)"
    font = _font(12, bold=True)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Place label past the arrow head along the same direction so it doesn't
    # cross the line — and offset perpendicularly to clear the head.
    head_pad = 18
    lx = ex + math.sin(rad) * head_pad - tw // 2
    ly = ey - math.cos(rad) * head_pad - th // 2
    pad = 3
    draw.rounded_rectangle(
        [(lx - pad, ly - pad), (lx + tw + pad, ly + th + pad)],
        radius=4, fill=pal["legend_bg"], outline=pal["wind"], width=1,
    )
    draw.text((lx, ly), label, fill=pal["wind"], font=font)


def _draw_legend(draw: ImageDraw.ImageDraw, pal: dict, scenario: Scenario) -> None:
    top = H - LEGEND_HEIGHT
    draw.rectangle([(0, top), (W, H)], fill=pal["legend_bg"], outline=pal["compass_ring"], width=1)

    f_bold = _font(15)
    f_reg = _font(13, bold=False)
    type_a = VESSEL_LABELS[scenario.vessel_a.vtype]
    type_b = VESSEL_LABELS[scenario.vessel_b.vtype]
    hdg_a = f"курс {scenario.vessel_a.heading}° {_compass_label(scenario.vessel_a.heading)}"
    hdg_b = f"курс {scenario.vessel_b.heading}° {_compass_label(scenario.vessel_b.heading)}"

    pad = 14
    chip_r = 13

    def _chip(x: float, y: float, vtype: VesselType, letter: str) -> None:
        draw.ellipse(
            [(x, y - chip_r), (x + 2 * chip_r, y + chip_r)],
            fill=VESSEL_COLORS[vtype], outline=VESSEL_DARK[vtype],
        )
        _text_centered(draw, (x + chip_r, y), letter, _font(15), WHITE)

    _chip(pad, top + LEGEND_HEIGHT // 2, scenario.vessel_a.vtype, "А")
    draw.text((pad + 2 * chip_r + 8, top + 8), f"А — {type_a}", fill=pal["letter_a"], font=f_bold)
    draw.text((pad + 2 * chip_r + 8, top + 28), hdg_a, fill=pal["label_text"], font=f_reg)

    bx = W // 2 + pad // 2
    _chip(bx, top + LEGEND_HEIGHT // 2, scenario.vessel_b.vtype, "Б")
    draw.text((bx + 2 * chip_r + 8, top + 8), f"Б — {type_b}", fill=pal["letter_b"], font=f_bold)
    draw.text((bx + 2 * chip_r + 8, top + 28), hdg_b, fill=pal["label_text"], font=f_reg)


# ── DAY mode vessel rendering ─────────────────────────────────────────────────

def _draw_vessel_day(
    draw: ImageDraw.ImageDraw,
    cx: float, cy: float,
    heading: int,
    vtype: VesselType,
    letter: str,
) -> None:
    rad = math.radians(heading)
    sz = VESSEL_SIZE

    local = [
        (0, -sz),                  # bow
        (sz * 0.55, sz * 0.55),    # stern starboard
        (0, sz * 0.30),            # stern notch
        (-sz * 0.55, sz * 0.55),   # stern port
    ]

    def rot(px: float, py: float) -> tuple[float, float]:
        s, c = math.sin(rad), math.cos(rad)
        return cx + px * c - py * s, cy + px * s + py * c

    # Shade the hull so А and Б are distinguishable even when both vessels
    # share a type. А lighter, Б darker; outline always uses the dark variant
    # so the silhouette stays crisp on the sea background.
    tint = A_TINT if letter == "А" else B_TINT
    color = _shade(VESSEL_COLORS[vtype], tint)
    dark = VESSEL_DARK[vtype]
    draw.polygon([rot(*p) for p in local], fill=color, outline=dark)

    bow_x, bow_y = rot(0, -sz)
    end_x = cx + math.sin(rad) * (sz + COURSE_LINE_LEN)
    end_y = cy - math.cos(rad) * (sz + COURSE_LINE_LEN)
    steps = 8
    for i in range(steps):
        if i % 2 == 0:
            t0, t1 = i / steps, (i + 0.55) / steps
            draw.line(
                [
                    (bow_x + (end_x - bow_x) * t0, bow_y + (end_y - bow_y) * t0),
                    (bow_x + (end_x - bow_x) * t1, bow_y + (end_y - bow_y) * t1),
                ],
                fill=dark, width=2,
            )

    # Letter sized below the hull's narrowest point so it never overflows.
    # sz=28 → font ≈ 13 pt (sz * 0.45).
    letter_pos = rot(0, sz * 0.05)
    letter_font = _font(int(sz * 0.45))
    _text_centered(draw, letter_pos, letter, letter_font, WHITE)


# ── NIGHT mode vessel rendering — navigation lights only ──────────────────────

def _glow_dot(
    overlay: Image.Image,
    cx: float, cy: float,
    color: tuple[int, int, int],
    core: int = 4,
    halo: int = 10,
    intensity: float = 1.0,
) -> None:
    """Soft glow: bright core surrounded by translucent halos.

    `intensity` scales the halo alpha (and slightly the core) — used to give
    А a brighter glow than Б so paired lights of the same colour at the
    same point in the scene don't look identical.
    """
    dr = ImageDraw.Draw(overlay, "RGBA")
    halo_alpha_peak = int(min(255, 110 * intensity))
    for r in range(halo, core, -2):
        alpha = int(halo_alpha_peak * (1 - (r - core) / max(1, halo - core)))
        dr.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            fill=(color[0], color[1], color[2], alpha),
        )
    core_alpha = int(min(255, 255 * intensity)) if intensity < 1 else 255
    dr.ellipse([(cx - core, cy - core), (cx + core, cy + core)],
               fill=(*color, core_alpha))


def _vessel_lights(vtype: VesselType, has_way: bool = True) -> list[tuple[str, tuple[int, int, int]]]:
    """Return a list of (position_key, colour) entries for one vessel's lights.

    position_key values:
      'mast'   — masthead light (forward, raised)
      'stern'  — stern light (aft)
      'port'   — port side light (red, left)
      'stbd'   — starboard side light (green, right)
      'allN'   — all-round, vertical position N (1 = lowest)
    """
    mast = ("mast", LIGHT_WHITE)
    stern = ("stern", LIGHT_WHITE)
    port = ("port", LIGHT_RED)
    stbd = ("stbd", LIGHT_GREEN)

    if vtype == VesselType.MOTOR:
        return [mast, port, stbd, stern] if has_way else []
    if vtype == VesselType.SAIL:
        # Rule 25: red/green/stern, no masthead
        return [port, stbd, stern] if has_way else []
    if vtype == VesselType.FISHING:
        # Rule 26: two all-round (red/white for non-trawling, simplified here)
        out = [("all1", LIGHT_WHITE), ("all2", LIGHT_RED)]
        if has_way:
            out += [port, stbd, stern]
        return out
    if vtype == VesselType.NUC:
        # Rule 27: two all-round red
        out = [("all1", LIGHT_RED), ("all2", LIGHT_RED)]
        if has_way:
            out += [port, stbd, stern]
        return out
    if vtype == VesselType.RAM:
        # Rule 27: three all-round red/white/red + masthead/side/stern if making way
        out = [("all1", LIGHT_RED), ("all2", LIGHT_WHITE), ("all3", LIGHT_RED)]
        if has_way:
            out += [mast, port, stbd, stern]
        return out
    return []


def _draw_vessel_night(
    overlay: Image.Image,
    cx: float, cy: float,
    heading: int,
    vtype: VesselType,
    letter: str,
    letter_color: tuple[int, int, int],
) -> None:
    fwd, stb = _heading_vectors(heading)

    # Distances chosen so a typical merchant/sailing vessel's lights are
    # clearly distinguishable at this canvas scale.
    mast_d   = 16
    stern_d  = 16
    side_fwd = 4
    side_lat = 11
    allround_step = 9

    def pos(forward: float = 0, lateral: float = 0) -> tuple[float, float]:
        return cx + fwd[0] * forward + stb[0] * lateral, cy + fwd[1] * forward + stb[1] * lateral

    positions = {
        "mast":  pos(forward=mast_d),
        "stern": pos(forward=-stern_d),
        "port":  pos(forward=side_fwd, lateral=-side_lat),
        "stbd":  pos(forward=side_fwd, lateral=side_lat),
    }
    # all-round lights stacked along the centerline of the canvas (vertical
    # stack in real life — flattened to slight forward offsets here so they
    # don't all overlap).
    for n in (1, 2, 3):
        positions[f"all{n}"] = pos(forward=allround_step * (n - 2))

    # А lights ~25% brighter than Б so a same-type pair stays distinguishable.
    intensity = 1.0 if letter == "А" else 0.65
    for key, color in _vessel_lights(vtype):
        px, py = positions[key]
        _glow_dot(overlay, px, py, color, core=4, halo=10, intensity=intensity)

    # Letter label next to the lights cluster (offset toward starboard so it
    # doesn't sit on top of any light).
    label_pos = pos(forward=-2, lateral=side_lat + 16)
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    letter_font = _font(16)
    bbox = overlay_draw.textbbox((0, 0), letter, font=letter_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    lx = label_pos[0] - tw // 2
    ly = label_pos[1] - th // 2
    pad = 3
    overlay_draw.rounded_rectangle(
        [(lx - pad, ly - pad), (lx + tw + pad, ly + th + pad)],
        radius=4, fill=(0, 0, 0, 160), outline=(*letter_color, 255), width=1,
    )
    overlay_draw.text((lx, ly), letter, fill=(*letter_color, 255), font=letter_font)


# ── Public API ────────────────────────────────────────────────────────────────

def render_scenario(scenario: Scenario, *, mode: str = "day") -> bytes:
    """Render a scenario to PNG bytes. `mode` is 'day' or 'night'."""
    pal = NIGHT if mode == "night" else DAY

    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)

    _draw_background(draw, pal)
    _draw_compass(draw, pal)

    ax, ay = _to_canvas(scenario.vessel_a.x, scenario.vessel_a.y)
    bx, by = _to_canvas(scenario.vessel_b.x, scenario.vessel_b.y)

    if mode == "night":
        # Lights need alpha for soft glow — composited onto the base image.
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _draw_vessel_night(overlay, ax, ay, scenario.vessel_a.heading,
                           scenario.vessel_a.vtype, "А", pal["letter_a"])
        _draw_vessel_night(overlay, bx, by, scenario.vessel_b.heading,
                           scenario.vessel_b.vtype, "Б", pal["letter_b"])
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
    else:
        _draw_vessel_day(draw, ax, ay, scenario.vessel_a.heading,
                         scenario.vessel_a.vtype, "А")
        _draw_vessel_day(draw, bx, by, scenario.vessel_b.heading,
                         scenario.vessel_b.vtype, "Б")

    _draw_wind(draw, pal, scenario.wind_dir)
    _draw_legend(draw, pal, scenario)

    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=pal["frame"], width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
