"""Renders COLREGs encounter scenarios to PNG using Pillow.

Canvas is 600×600 px (square — scenes need equal horizontal/vertical space
for the compass rose).

Layout:
  - Compass rose in the centre (cardinal labels, subtle ring)
  - Wind arrow + text in the top-right corner (always at the same position
    so the eye doesn't hunt for it)
  - Two vessels placed away from centre, each with a big letter (А / Б)
    drawn inside the hull — self-labelling, no overlapping pins
  - Dashed course-projection line forward from the bow
  - Bottom legend: vessel type + heading in degrees with cardinal name
    (this is where the student reads off course info — keeps the image
    above clean)

Coordinate system:
  - Canvas: (0, 0) top-left, (600, 600) bottom-right
  - Scenario data: unit square 0..1, y increases downward
  - Compass: 0° North = up, clockwise
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

from app.training.colregs.data import Scenario, VESSEL_LABELS, VesselType, _compass_label

# ── Canvas constants ──────────────────────────────────────────────────────────

W = H = 600
CX = CY = 300          # compass centre
COMPASS_R = 230        # compass rose radius
VESSEL_SIZE = 28       # half-length of vessel arrow (was 18 → too small)
COURSE_LINE_LEN = 70   # dashed course projection line length
LEGEND_HEIGHT = 56     # bottom legend strip

# ── Colours ───────────────────────────────────────────────────────────────────

SEA = (216, 236, 250)
COMPASS_RING = (110, 145, 195)
COMPASS_TEXT = (50, 90, 150)
GRID = (200, 224, 240)
WIND_COLOR = (28, 145, 70)
LEGEND_BG = (245, 250, 254)

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

LABEL_A_COLOR = (28, 70, 175)
LABEL_B_COLOR = (175, 50, 30)
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)
DARK_GRAY = (60, 60, 60)

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
    """Convert unit-square coordinates to canvas pixels (above the legend)."""
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


# ── Sub-draw routines ─────────────────────────────────────────────────────────

def _draw_sea(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([(0, 0), (W, H)], fill=SEA)
    # subtle grid every 60 px — gives a sense of scale without dominating
    for i in range(0, W + 1, 60):
        draw.line([(i, 0), (i, H - LEGEND_HEIGHT)], fill=GRID, width=1)
    for i in range(0, H - LEGEND_HEIGHT + 1, 60):
        draw.line([(0, i), (W, i)], fill=GRID, width=1)


def _draw_compass(draw: ImageDraw.ImageDraw) -> None:
    cy = CY - LEGEND_HEIGHT // 2  # compass shifts up to share canvas with legend
    draw.ellipse(
        [(CX - COMPASS_R, cy - COMPASS_R), (CX + COMPASS_R, cy + COMPASS_R)],
        outline=COMPASS_RING, width=1,
    )
    draw.ellipse([(CX - 3, cy - 3), (CX + 3, cy + 3)], fill=COMPASS_RING)

    # Tick marks every ~22° (16 directions); cardinals are longer/thicker.
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
        draw.line([(ix, iy), (ox, oy)], fill=COMPASS_RING, width=2 if is_card else 1)

    main_f = _font(17)
    small_f = _font(11)
    for deg, label in {0: "С", 90: "В", 180: "Ю", 270: "З"}.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 18)
        ly = cy - math.cos(rad) * (COMPASS_R + 18)
        _text_centered(draw, (lx, ly), label, main_f, COMPASS_TEXT)
    for deg, label in {45: "СВ", 135: "ЮВ", 225: "ЮЗ", 315: "СЗ"}.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 16)
        ly = cy - math.cos(rad) * (COMPASS_R + 16)
        _text_centered(draw, (lx, ly), label, small_f, COMPASS_TEXT)


def _draw_wind(draw: ImageDraw.ImageDraw, wind_dir: int) -> None:
    """Fixed-position wind indicator in the top-left.

    Always drawn at the same spot so the student doesn't have to hunt for
    it. Tells direction by both the arrow and a compass-name text.
    """
    box_w, box_h = 150, 42
    x, y = 12, 12
    draw.rounded_rectangle(
        [(x, y), (x + box_w, y + box_h)],
        radius=6, fill=WHITE, outline=WIND_COLOR, width=2,
    )
    # arrow inside the badge: small compass with arrow indicating wind direction
    arrow_cx, arrow_cy = x + 22, y + box_h // 2
    rad = math.radians(wind_dir)
    # Wind blows from wind_dir → arrow drawn pointing in OPPOSITE direction,
    # tail at wind_dir side, head at 180° opposite.
    tail_x = arrow_cx + math.sin(rad) * 12
    tail_y = arrow_cy - math.cos(rad) * 12
    head_x = arrow_cx - math.sin(rad) * 14
    head_y = arrow_cy + math.cos(rad) * 14
    draw.line([(tail_x, tail_y), (head_x, head_y)], fill=WIND_COLOR, width=3)
    # arrowhead at head
    dx, dy = head_x - tail_x, head_y - tail_y
    length = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    base_x, base_y = head_x - ux * 7, head_y - uy * 7
    half = 4
    p1 = (base_x - uy * half, base_y + ux * half)
    p2 = (base_x + uy * half, base_y - ux * half)
    draw.polygon([(head_x, head_y), p1, p2], fill=WIND_COLOR)

    label_font = _font(13)
    label = f"Ветер: {_compass_label(wind_dir)} ({wind_dir}°)"
    draw.text((x + 44, y + 12), label, fill=WIND_COLOR, font=label_font)


def _draw_vessel(
    draw: ImageDraw.ImageDraw,
    cx: float, cy: float,
    heading: int,
    vtype: VesselType,
    letter: str,
    letter_color: tuple[int, int, int],
) -> None:
    """A filled arrow hull oriented along `heading`, with a big letter inside it.

    Internal-letter labelling means we don't need a separate floating pin,
    so there's no overlap between A/Б labels and the dashed course line.
    """
    rad = math.radians(heading)
    sz = VESSEL_SIZE

    # Hull polygon in local coords (bow at top, stern at bottom).
    local = [
        (0, -sz),                  # bow
        (sz * 0.55, sz * 0.55),    # stern starboard
        (0, sz * 0.30),            # stern notch
        (-sz * 0.55, sz * 0.55),   # stern port
    ]

    def rot(px: float, py: float) -> tuple[float, float]:
        s, c = math.sin(rad), math.cos(rad)
        return cx + px * c - py * s, cy + px * s + py * c

    color = VESSEL_COLORS[vtype]
    dark = VESSEL_DARK[vtype]
    draw.polygon([rot(*p) for p in local], fill=color, outline=dark)

    # Dashed course-projection line from bow.
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

    # Vessel letter inside the hull body (slight stern offset so it's centred on the bulk).
    letter_pos = rot(0, sz * 0.05)
    letter_font = _font(int(sz * 1.1))
    _text_centered(draw, letter_pos, letter, letter_font, WHITE)


def _draw_legend(draw: ImageDraw.ImageDraw, scenario: Scenario) -> None:
    """Bottom info strip — colour-coded by vessel."""
    top = H - LEGEND_HEIGHT
    draw.rectangle([(0, top), (W, H)], fill=LEGEND_BG, outline=COMPASS_RING, width=1)

    f_bold = _font(15)
    f_reg = _font(13, bold=False)

    type_a = VESSEL_LABELS[scenario.vessel_a.vtype]
    type_b = VESSEL_LABELS[scenario.vessel_b.vtype]
    hdg_a = f"курс {scenario.vessel_a.heading}° {_compass_label(scenario.vessel_a.heading)}"
    hdg_b = f"курс {scenario.vessel_b.heading}° {_compass_label(scenario.vessel_b.heading)}"

    pad = 14
    col_w = (W - 3 * pad) // 2

    # А — left half
    chip_r = 13
    draw.ellipse(
        [(pad, top + LEGEND_HEIGHT // 2 - chip_r),
         (pad + 2 * chip_r, top + LEGEND_HEIGHT // 2 + chip_r)],
        fill=VESSEL_COLORS[scenario.vessel_a.vtype], outline=VESSEL_DARK[scenario.vessel_a.vtype],
    )
    _text_centered(
        draw, (pad + chip_r, top + LEGEND_HEIGHT // 2), "А", _font(15), WHITE
    )
    draw.text((pad + 2 * chip_r + 8, top + 8), f"А — {type_a}", fill=LABEL_A_COLOR, font=f_bold)
    draw.text((pad + 2 * chip_r + 8, top + 28), hdg_a, fill=DARK_GRAY, font=f_reg)

    # Б — right half
    bx_chip = W // 2 + pad // 2
    draw.ellipse(
        [(bx_chip, top + LEGEND_HEIGHT // 2 - chip_r),
         (bx_chip + 2 * chip_r, top + LEGEND_HEIGHT // 2 + chip_r)],
        fill=VESSEL_COLORS[scenario.vessel_b.vtype], outline=VESSEL_DARK[scenario.vessel_b.vtype],
    )
    _text_centered(
        draw, (bx_chip + chip_r, top + LEGEND_HEIGHT // 2), "Б", _font(15), WHITE
    )
    draw.text((bx_chip + 2 * chip_r + 8, top + 8), f"Б — {type_b}", fill=LABEL_B_COLOR, font=f_bold)
    draw.text((bx_chip + 2 * chip_r + 8, top + 28), hdg_b, fill=DARK_GRAY, font=f_reg)


# ── Public API ────────────────────────────────────────────────────────────────

def render_scenario(scenario: Scenario) -> bytes:
    """Render a scenario image and return PNG bytes."""
    img = Image.new("RGB", (W, H), SEA)
    draw = ImageDraw.Draw(img)

    _draw_sea(draw)
    _draw_compass(draw)

    ax, ay = _to_canvas(scenario.vessel_a.x, scenario.vessel_a.y)
    bx, by = _to_canvas(scenario.vessel_b.x, scenario.vessel_b.y)
    _draw_vessel(draw, ax, ay, scenario.vessel_a.heading, scenario.vessel_a.vtype, "А", LABEL_A_COLOR)
    _draw_vessel(draw, bx, by, scenario.vessel_b.heading, scenario.vessel_b.vtype, "Б", LABEL_B_COLOR)

    _draw_wind(draw, scenario.wind_dir)
    _draw_legend(draw, scenario)

    # Outer frame
    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=(140, 165, 200), width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
