"""Renders COLREGs encounter scenarios to PNG using Pillow.

Canvas is 600×600 px (square, unlike the 600×400 flag format — scenes
need equal horizontal/vertical space for the compass rose).

Coordinate system:
  - Canvas: 0,0 top-left, 600,600 bottom-right
  - Scenario data: unit square 0..1, y increases downward
  - Compass: 0° North = up, clockwise

No sailing geometry is shown on purpose — the student must reason about
tacks, galses and wind angles themselves. The wind arrow is shown so
the student knows where the wind is coming from.
"""

from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.training.colregs.data import Scenario, VesselType

# ── Canvas constants ──────────────────────────────────────────────────────────

W = H = 600
CX = CY = 300          # compass centre
COMPASS_R = 230        # compass rose radius
VESSEL_SIZE = 18       # half-length of vessel arrow
COURSE_LINE_LEN = 60   # dashed course projection line length

# ── Colours ───────────────────────────────────────────────────────────────────

SEA = (210, 235, 250)
COMPASS_RING = (100, 140, 190)
COMPASS_TEXT = (40, 80, 140)
GRID = (190, 220, 240)
WIND_COLOR = (30, 160, 80)

VESSEL_COLORS: dict[VesselType, tuple[int, int, int]] = {
    VesselType.MOTOR:   (180, 80,  20),
    VesselType.SAIL:    (20,  100, 190),
    VesselType.FISHING: (30,  140, 60),
    VesselType.NUC:     (140, 30,  140),
    VesselType.RAM:     (180, 140, 20),
}

VESSEL_DARK: dict[VesselType, tuple[int, int, int]] = {
    VesselType.MOTOR:   (120, 50,  10),
    VesselType.SAIL:    (10,  60,  140),
    VesselType.FISHING: (10,  90,  30),
    VesselType.NUC:     (90,  10,  90),
    VesselType.RAM:     (120, 90,  10),
}

LABEL_A_COLOR = (20, 60, 160)
LABEL_B_COLOR = (160, 40, 20)
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)
DARK_GRAY = (60, 60, 60)


# ── Font helpers ──────────────────────────────────────────────────────────────

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

_FONT_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    paths = _FONT_PATHS if bold else _FONT_REGULAR_PATHS
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _to_canvas(x: float, y: float) -> tuple[float, float]:
    """Convert unit-square coordinates to canvas pixels."""
    margin = 40
    size = W - 2 * margin
    return margin + x * size, margin + y * size


def _hdg_to_vec(hdg: int) -> tuple[float, float]:
    """Unit vector in the direction of heading (nautical degrees)."""
    rad = math.radians(hdg)
    return math.sin(rad), -math.cos(rad)


def _rotate_point(px: float, py: float, cx: float, cy: float,
                  angle_rad: float) -> tuple[float, float]:
    s, c = math.sin(angle_rad), math.cos(angle_rad)
    dx, dy = px - cx, py - cy
    return cx + dx * c - dy * s, cy + dx * s + dy * c


# ── Sub-draw routines ─────────────────────────────────────────────────────────

def _draw_sea(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([(0, 0), (W, H)], fill=SEA)
    # Subtle grid
    for i in range(0, W + 1, 60):
        draw.line([(i, 0), (i, H)], fill=GRID, width=1)
        draw.line([(0, i), (W, i)], fill=GRID, width=1)


def _draw_compass(draw: ImageDraw.ImageDraw) -> None:
    # Outer ring
    draw.ellipse(
        [(CX - COMPASS_R, CY - COMPASS_R), (CX + COMPASS_R, CY + COMPASS_R)],
        outline=COMPASS_RING, width=1,
    )
    # Centre dot
    draw.ellipse([(CX - 3, CY - 3), (CX + 3, CY + 3)], fill=COMPASS_RING)

    font_main = _load_font(16)
    font_small = _load_font(11)

    # Cardinal and intercardinal tick marks and labels
    for deg in range(0, 360, 22):
        rad = math.radians(deg)
        sin_d, cos_d = math.sin(rad), -math.cos(rad)

        is_cardinal = (deg % 90 == 0)
        is_intercardinal = (deg % 45 == 0 and not is_cardinal)
        tick_inner = COMPASS_R - (10 if is_cardinal else (6 if is_intercardinal else 3))

        ix = CX + sin_d * tick_inner
        iy = CY + cos_d * tick_inner
        ox = CX + sin_d * COMPASS_R
        oy = CY + cos_d * COMPASS_R
        draw.line([(ix, iy), (ox, oy)], fill=COMPASS_RING, width=(2 if is_cardinal else 1))

    # Cardinal labels
    cardinals = {0: "С", 90: "В", 180: "Ю", 270: "З"}
    for deg, label in cardinals.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 18)
        ly = CY - math.cos(rad) * (COMPASS_R + 18)
        bbox = draw.textbbox((0, 0), label, font=font_main)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((lx - tw // 2, ly - th // 2), label,
                  fill=COMPASS_TEXT, font=font_main)

    # Intercardinal labels (smaller)
    intercardinals = {45: "СВ", 135: "ЮВ", 225: "ЮЗ", 315: "СЗ"}
    for deg, label in intercardinals.items():
        rad = math.radians(deg)
        lx = CX + math.sin(rad) * (COMPASS_R + 16)
        ly = CY - math.cos(rad) * (COMPASS_R + 16)
        bbox = draw.textbbox((0, 0), label, font=font_small)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((lx - tw // 2, ly - th // 2), label,
                  fill=COMPASS_TEXT, font=font_small)


def _draw_wind(draw: ImageDraw.ImageDraw, wind_dir: int) -> None:
    """Draw a short arrow FROM the wind direction TOWARD centre (wind blows toward arrow tip)."""
    rad = math.radians(wind_dir)
    # Wind comes FROM wind_dir, so arrow points in opposite direction (toward where wind goes)
    # We draw the arrow at the edge of compass rose pointing inward
    start_r = COMPASS_R - 20
    end_r = COMPASS_R - 55

    sx = CX + math.sin(rad) * start_r
    sy = CY - math.cos(rad) * start_r
    ex = CX + math.sin(rad) * end_r
    ey = CY - math.cos(rad) * end_r

    draw.line([(sx, sy), (ex, ey)], fill=WIND_COLOR, width=3)

    # Arrowhead at the end (pointing inward = direction wind blows TO)
    arrow_len = 12
    arrow_half = 5
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length > 0:
        ux, uy = dx / length, dy / length
        # Arrow tip
        tip_x, tip_y = ex, ey
        # Base of arrowhead
        base_x = tip_x - ux * arrow_len
        base_y = tip_y - uy * arrow_len
        left_x = base_x - uy * arrow_half
        left_y = base_y + ux * arrow_half
        right_x = base_x + uy * arrow_half
        right_y = base_y - ux * arrow_half
        draw.polygon(
            [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)],
            fill=WIND_COLOR,
        )

    # Wind label next to the arrow origin
    font = _load_font(11, bold=False)
    lx = CX + math.sin(rad) * (COMPASS_R - 10)
    ly = CY - math.cos(rad) * (COMPASS_R - 10)
    label = "ветер"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Offset label perpendicular to wind direction so it doesn't overlap arrow
    perp_x = math.cos(rad) * 14
    perp_y = math.sin(rad) * 14
    draw.text((lx - tw // 2 + perp_x, ly - th // 2 + perp_y),
              label, fill=WIND_COLOR, font=font)


def _draw_vessel(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    cx: float, cy: float,
    heading: int,
    vtype: VesselType,
    label: str,
    label_color: tuple[int, int, int],
) -> None:
    """Draw a vessel as a filled arrow (hull silhouette) pointing in heading direction."""
    rad = math.radians(heading)
    sz = VESSEL_SIZE

    # Arrow shape in local coords (pointing up = North = 0°):
    # bow at (0, -sz), stern corners at (±sz*0.45, +sz*0.55)
    # stern notch at (0, +sz*0.28) — gives it a hull shape
    local_points = [
        (0, -sz),                   # bow
        (sz * 0.45, sz * 0.55),     # stern starboard
        (0, sz * 0.28),             # stern notch
        (-sz * 0.45, sz * 0.55),    # stern port
    ]

    def _rotate(px: float, py: float) -> tuple[float, float]:
        s, c = math.sin(rad), math.cos(rad)
        return cx + px * c - py * s, cy + px * s + py * c

    rotated = [_rotate(px, py) for px, py in local_points]

    color = VESSEL_COLORS[vtype]
    dark = VESSEL_DARK[vtype]

    draw.polygon(rotated, fill=color, outline=dark)

    # Dashed course projection line (bow forward)
    bow_x = cx + math.sin(rad) * sz
    bow_y = cy - math.cos(rad) * sz
    end_x = cx + math.sin(rad) * (sz + COURSE_LINE_LEN)
    end_y = cy - math.cos(rad) * (sz + COURSE_LINE_LEN)

    # Manual dashes
    steps = 8
    for i in range(steps):
        if i % 2 == 0:
            t0, t1 = i / steps, (i + 0.5) / steps
            x0 = bow_x + (end_x - bow_x) * t0
            y0 = bow_y + (end_y - bow_y) * t0
            x1 = bow_x + (end_x - bow_x) * t1
            y1 = bow_y + (end_y - bow_y) * t1
            draw.line([(x0, y0), (x1, y1)], fill=dark, width=1)

    # Vessel label (А / Б)
    font_label = _load_font(18)
    # Place label offset from bow
    label_dist = sz + COURSE_LINE_LEN + 14
    lx = cx + math.sin(rad) * label_dist
    ly = cy - math.cos(rad) * label_dist
    bbox = draw.textbbox((0, 0), label, font=font_label)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # White background pill for readability
    pad = 3
    draw.rounded_rectangle(
        [(lx - tw // 2 - pad, ly - th // 2 - pad),
         (lx + tw // 2 + pad, ly + th // 2 + pad)],
        radius=4, fill=WHITE, outline=label_color, width=1,
    )
    draw.text((lx - tw // 2, ly - th // 2), label,
              fill=label_color, font=font_label)


def _draw_heading_badge(
    draw: ImageDraw.ImageDraw,
    cx: float, cy: float,
    heading: int,
    vtype: VesselType,
) -> None:
    """Small course badge near the vessel showing its heading in degrees."""
    font = _load_font(11, bold=False)
    from app.training.colregs.data import _compass_label  # avoid circular at module level
    text = f"{heading}° {_compass_label(heading)}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Place badge below and slightly right of the vessel centre
    bx = cx + 14
    by = cy + VESSEL_SIZE + 4
    pad = 3
    draw.rounded_rectangle(
        [(bx - pad, by - pad), (bx + tw + pad, by + th + pad)],
        radius=3,
        fill=(*VESSEL_COLORS[vtype], 200),  # type: ignore[arg-type]
        outline=VESSEL_DARK[vtype],
        width=1,
    )
    draw.text((bx, by), text, fill=WHITE, font=font)


def _draw_legend(draw: ImageDraw.ImageDraw, scenario: Scenario) -> None:
    """Bottom legend strip: vessel type labels."""
    font = _load_font(13, bold=False)
    font_bold = _load_font(13)

    from app.training.colregs.data import VESSEL_LABELS
    label_a = VESSEL_LABELS[scenario.vessel_a.vtype]
    label_b = VESSEL_LABELS[scenario.vessel_b.vtype]

    y = H - 32
    pad = 10

    # A legend
    text_a = f"А — {label_a}"
    draw.text((pad, y), text_a, fill=LABEL_A_COLOR, font=font_bold)

    # B legend (right-aligned)
    text_b = f"Б — {label_b}"
    bbox = draw.textbbox((0, 0), text_b, font=font_bold)
    tw = bbox[2] - bbox[0]
    draw.text((W - pad - tw, y), text_b, fill=LABEL_B_COLOR, font=font_bold)

    # Scenario type label (centre)
    bbox_c = draw.textbbox((0, 0), scenario.description, font=font)
    tw_c = bbox_c[2] - bbox_c[0]
    draw.text((W // 2 - tw_c // 2, y), scenario.description,
              fill=DARK_GRAY, font=font)


# ── Public API ────────────────────────────────────────────────────────────────

def render_scenario(scenario: Scenario) -> bytes:
    """Render a scenario image and return PNG bytes."""
    img = Image.new("RGB", (W, H), SEA)
    draw = ImageDraw.Draw(img)

    _draw_sea(draw)
    _draw_compass(draw)
    _draw_wind(draw, scenario.wind_dir)

    # Convert unit coords to canvas coords
    ax, ay = _to_canvas(scenario.vessel_a.x, scenario.vessel_a.y)
    bx, by = _to_canvas(scenario.vessel_b.x, scenario.vessel_b.y)

    _draw_vessel(draw, img, ax, ay,
                 scenario.vessel_a.heading, scenario.vessel_a.vtype,
                 "А", LABEL_A_COLOR)
    _draw_vessel(draw, img, bx, by,
                 scenario.vessel_b.heading, scenario.vessel_b.vtype,
                 "Б", LABEL_B_COLOR)

    _draw_heading_badge(draw, ax, ay,
                        scenario.vessel_a.heading, scenario.vessel_a.vtype)
    _draw_heading_badge(draw, bx, by,
                        scenario.vessel_b.heading, scenario.vessel_b.vtype)

    _draw_legend(draw, scenario)

    # Wind direction text in corner
    font_sm = _load_font(11, bold=False)
    from app.training.colregs.data import _compass_label
    wind_text = f"Ветер: с {_compass_label(scenario.wind_dir)} ({scenario.wind_dir}°)"
    draw.text((8, 8), wind_text, fill=WIND_COLOR, font=font_sm)

    # Border
    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=(130, 160, 190), width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
