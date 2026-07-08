"""Renders МСС-65 non-letter pennants (numerals, substitutes, answering).

Designs here are programmatic MVP approximations of the standard ICS pennant
artwork — they're visually distinct and useful for training. Final SVG assets
should replace these once available; the per-entry builder map below is the
single seam to swap.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from app.config import settings
from app.training.mcs65.flag_renderer import (
    BLACK,
    BLUE,
    BORDER,
    HEIGHT,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    _draw_checkerboard,
    CHECKER_LIGHT,
)

# Numeral / substitute / answering pennants are long isosceles triangles.
PENNANT_WIDTH = WIDTH
PENNANT_HEIGHT = HEIGHT


def _rect_canvas(fill: tuple[int, int, int] = WHITE) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (PENNANT_WIDTH, PENNANT_HEIGHT), fill)
    return img, ImageDraw.Draw(img)


def _horizontal(colors: list[tuple[int, int, int]]) -> Image.Image:
    img, draw = _rect_canvas()
    last = len(colors) - 1
    y = 0
    for i, color in enumerate(colors):
        h = PENNANT_HEIGHT - y if i == last else PENNANT_HEIGHT // len(colors)
        draw.rectangle([(0, y), (PENNANT_WIDTH, y + h)], fill=color)
        y += h
    return img


def _vertical(colors: list[tuple[int, int, int]]) -> Image.Image:
    img, draw = _rect_canvas()
    n = len(colors)
    for i, color in enumerate(colors):
        x1 = PENNANT_WIDTH * i // n
        x2 = PENNANT_WIDTH * (i + 1) // n
        draw.rectangle([(x1, 0), (x2, PENNANT_HEIGHT)], fill=color)
    return img


def _solid_with_cross(bg: tuple[int, int, int], cross: tuple[int, int, int]) -> Image.Image:
    img, draw = _rect_canvas(bg)
    thick = PENNANT_HEIGHT // 4
    # Horizontal arm — placed left of the taper so it stays visible after masking.
    draw.rectangle(
        [(0, (PENNANT_HEIGHT - thick) // 2), (PENNANT_WIDTH // 2, (PENNANT_HEIGHT + thick) // 2)],
        fill=cross,
    )
    # Vertical arm
    draw.rectangle(
        [(PENNANT_WIDTH // 4 - thick // 2, 0), (PENNANT_WIDTH // 4 + thick // 2, PENNANT_HEIGHT)],
        fill=cross,
    )
    return img


def _solid_with_saltire(bg: tuple[int, int, int], cross: tuple[int, int, int]) -> Image.Image:
    img, draw = _rect_canvas(bg)
    thick = PENNANT_HEIGHT // 6
    half = PENNANT_WIDTH // 2  # only saltire over the hoist half — taper would distort lines
    draw.polygon(
        [(0, 0), (thick, 0), (half, PENNANT_HEIGHT - thick), (half - thick, PENNANT_HEIGHT)],
        fill=cross,
    )
    draw.polygon(
        [(0, PENNANT_HEIGHT), (0, PENNANT_HEIGHT - thick), (half - thick, 0), (half, 0)],
        fill=cross,
    )
    return img


def _diagonal_split(upper: tuple[int, int, int], lower: tuple[int, int, int]) -> Image.Image:
    img, draw = _rect_canvas()
    draw.polygon([(0, 0), (PENNANT_WIDTH, 0), (PENNANT_WIDTH, PENNANT_HEIGHT)], fill=upper)
    draw.polygon([(0, 0), (0, PENNANT_HEIGHT), (PENNANT_WIDTH, PENNANT_HEIGHT)], fill=lower)
    return img


def _diagonal_stripe(bg: tuple[int, int, int], stripe: tuple[int, int, int]) -> Image.Image:
    """Solid background with one diagonal band from lower-hoist to upper-fly."""
    img, draw = _rect_canvas(bg)
    thick = PENNANT_HEIGHT // 4
    draw.polygon(
        [
            (0, PENNANT_HEIGHT),
            (thick, PENNANT_HEIGHT),
            (PENNANT_WIDTH, thick // 2),
            (PENNANT_WIDTH - thick, 0),
            (0, PENNANT_HEIGHT - thick),
        ],
        fill=stripe,
    )
    return img


def _solid(color: tuple[int, int, int]) -> Image.Image:
    img, _ = _rect_canvas(color)
    return img


def _mask_to_pennant(rect: Image.Image) -> Image.Image:
    """Crop a rectangle to a long isosceles-triangle pennant pointing to the fly side.

    Area outside the triangle is filled with a light/dark checker so the
    pennant's shape is obvious — same convention as graphic-editor
    «transparent» pattern.
    """
    canvas = Image.new("RGB", (PENNANT_WIDTH, PENNANT_HEIGHT), CHECKER_LIGHT)
    canvas_draw = ImageDraw.Draw(canvas)
    _draw_checkerboard(canvas_draw, 0, 0, PENNANT_WIDTH, PENNANT_HEIGHT)
    mask = Image.new("L", (PENNANT_WIDTH, PENNANT_HEIGHT), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon(
        [(0, 0), (PENNANT_WIDTH, PENNANT_HEIGHT // 2), (0, PENNANT_HEIGHT)],
        fill=255,
    )
    canvas.paste(rect, (0, 0), mask)
    out_draw = ImageDraw.Draw(canvas)
    out_draw.polygon(
        [(0, 0), (PENNANT_WIDTH, PENNANT_HEIGHT // 2), (0, PENNANT_HEIGHT)],
        outline=BLACK,
        width=BORDER,
    )
    return canvas


def _mask_to_swallow(rect: Image.Image) -> Image.Image:
    """Crop a rectangle to swallow-tail (used for the 1st substitute in some references).

    Currently unused but kept available for future expansion.
    """
    notch = PENNANT_WIDTH // 5
    canvas = Image.new("RGB", (PENNANT_WIDTH, PENNANT_HEIGHT), WHITE)
    mask = Image.new("L", (PENNANT_WIDTH, PENNANT_HEIGHT), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon(
        [
            (0, 0),
            (PENNANT_WIDTH, 0),
            (PENNANT_WIDTH - notch, PENNANT_HEIGHT // 2),
            (PENNANT_WIDTH, PENNANT_HEIGHT),
            (0, PENNANT_HEIGHT),
        ],
        fill=255,
    )
    canvas.paste(rect, (0, 0), mask)
    return canvas


# Pattern for each pennant. Each builder returns a *rectangular* image; the
# `_mask_to_pennant` step gives it the triangular shape uniformly.
_PATTERNS: dict[str, Callable[[], Image.Image]] = {
    # Numerals 0–9 (МСС-65 cipher pennants).
    "N0": lambda: _horizontal([YELLOW, RED]),
    "N1": lambda: _horizontal([WHITE, RED]),
    "N2": lambda: _horizontal([BLUE, WHITE, BLUE]),
    "N3": lambda: _horizontal([RED, WHITE, BLUE]),
    "N4": lambda: _solid_with_cross(RED, WHITE),
    "N5": lambda: _diagonal_split(BLUE, YELLOW),
    "N6": lambda: _horizontal([BLACK, WHITE, BLACK]),
    "N7": lambda: _diagonal_stripe(YELLOW, RED),
    "N8": lambda: _solid_with_saltire(WHITE, RED),
    "N9": lambda: _vertical([YELLOW, BLUE, YELLOW]),
    # Substitute pennants.
    "S1": lambda: _horizontal([YELLOW, BLUE]),
    "S2": lambda: _horizontal([BLUE, WHITE, BLUE]),
    "S3": lambda: _horizontal([BLACK, RED]),
    # Answering / Code pennant — five vertical stripes red/white/red/white/red.
    "AP": lambda: _vertical([RED, WHITE, RED, WHITE, RED]),
}


def render(code: str) -> Path:
    """Render a pennant for `code` and return the cached PNG path."""
    settings.flags_dir.mkdir(parents=True, exist_ok=True)
    path = settings.flags_dir / f"pennant_{code}.png"
    if path.exists():
        return path
    builder = _PATTERNS.get(code)
    if builder is None:
        raise KeyError(f"no pennant renderer for {code!r}")
    img = _mask_to_pennant(builder())
    img.save(path, format="PNG", optimize=True)
    return path


def prerender_all() -> None:
    for code in _PATTERNS:
        render(code)
