"""Renders МСС-65 alphabet flags to PNG using Pillow.

Each flag is drawn programmatically from a structured spec, so the bot ships
without binary assets. Renders are cached on disk in settings.flags_dir.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import settings

WIDTH = 600
HEIGHT = 400
BORDER = 4

# Colour palette used across МСС flags.
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (206, 17, 38)
BLUE = (0, 56, 168)
YELLOW = (255, 205, 0)


def _new() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    return img, ImageDraw.Draw(img)


def _frame(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], outline=BLACK, width=BORDER)


def _solid(color: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=color)
    _frame(draw)
    return img


def _horizontal_stripes(colors: list[tuple[int, int, int]], weights: list[int] | None = None) -> Image.Image:
    img, draw = _new()
    w = weights or [1] * len(colors)
    total = sum(w)
    y = 0
    last_idx = len(colors) - 1
    for idx, (color, weight) in enumerate(zip(colors, w, strict=True)):
        # Last stripe extends to bottom to absorb any rounding leftover.
        h = HEIGHT - y if idx == last_idx else int(HEIGHT * weight / total)
        draw.rectangle([(0, y), (WIDTH, y + h)], fill=color)
        y += h
    _frame(draw)
    return img


def _vertical_stripes(colors: list[tuple[int, int, int]]) -> Image.Image:
    img, draw = _new()
    n = len(colors)
    for i, color in enumerate(colors):
        x1 = WIDTH * i // n
        x2 = WIDTH * (i + 1) // n
        draw.rectangle([(x1, 0), (x2, HEIGHT)], fill=color)
    _frame(draw)
    return img


def _quartered(tl: tuple[int, int, int], tr: tuple[int, int, int], bl: tuple[int, int, int], br: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    mx, my = WIDTH // 2, HEIGHT // 2
    draw.rectangle([(0, 0), (mx, my)], fill=tl)
    draw.rectangle([(mx, 0), (WIDTH, my)], fill=tr)
    draw.rectangle([(0, my), (mx, HEIGHT)], fill=bl)
    draw.rectangle([(mx, my), (WIDTH, HEIGHT)], fill=br)
    _frame(draw)
    return img


def _square_on(bg: tuple[int, int, int], square: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg)
    side = HEIGHT // 2
    x = (WIDTH - side) // 2
    y = (HEIGHT - side) // 2
    draw.rectangle([(x, y), (x + side, y + side)], fill=square)
    _frame(draw)
    return img


def _circle_on(bg: tuple[int, int, int], circle: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg)
    r = HEIGHT // 4
    cx, cy = WIDTH // 2, HEIGHT // 2
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=circle)
    _frame(draw)
    return img


def _diamond_on(bg: tuple[int, int, int], shape: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg)
    cx, cy = WIDTH // 2, HEIGHT // 2
    dx, dy = WIDTH // 4, HEIGHT // 3
    draw.polygon(
        [(cx, cy - dy), (cx + dx, cy), (cx, cy + dy), (cx - dx, cy)],
        fill=shape,
    )
    _frame(draw)
    return img


def _cross(bg: tuple[int, int, int], cross: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg)
    thick_h = HEIGHT // 4
    thick_w = HEIGHT // 4  # equal arm width
    draw.rectangle([(0, (HEIGHT - thick_h) // 2), (WIDTH, (HEIGHT + thick_h) // 2)], fill=cross)
    draw.rectangle([((WIDTH - thick_w) // 2, 0), ((WIDTH + thick_w) // 2, HEIGHT)], fill=cross)
    _frame(draw)
    return img


def _saltire(bg: tuple[int, int, int], cross: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg)
    thick = HEIGHT // 6
    # Two diagonal bands
    draw.polygon(
        [(0, 0), (thick, 0), (WIDTH, HEIGHT - thick), (WIDTH - thick, HEIGHT)],
        fill=cross,
    )
    draw.polygon(
        [(0, HEIGHT), (0, HEIGHT - thick), (WIDTH - thick, 0), (WIDTH, 0)],
        fill=cross,
    )
    _frame(draw)
    return img


def _diagonal_split(upper: tuple[int, int, int], lower: tuple[int, int, int]) -> Image.Image:
    """Split flag along the diagonal from top-left to bottom-right."""
    img, draw = _new()
    # upper-right triangle
    draw.polygon([(0, 0), (WIDTH, 0), (WIDTH, HEIGHT)], fill=upper)
    # lower-left triangle
    draw.polygon([(0, 0), (0, HEIGHT), (WIDTH, HEIGHT)], fill=lower)
    _frame(draw)
    return img


def _checkerboard(cols: int, rows: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    for r in range(rows):
        for c in range(cols):
            x1 = WIDTH * c // cols
            x2 = WIDTH * (c + 1) // cols
            y1 = HEIGHT * r // rows
            y2 = HEIGHT * (r + 1) // rows
            color = c1 if (r + c) % 2 == 0 else c2
            draw.rectangle([(x1, y1), (x2, y2)], fill=color)
    _frame(draw)
    return img


def _concentric_rects(outer: tuple[int, int, int], mid: tuple[int, int, int], inner: tuple[int, int, int]) -> Image.Image:
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=outer)
    pad_x, pad_y = WIDTH // 6, HEIGHT // 6
    draw.rectangle([(pad_x, pad_y), (WIDTH - pad_x, HEIGHT - pad_y)], fill=mid)
    pad_x2, pad_y2 = WIDTH // 3, HEIGHT // 3
    draw.rectangle([(pad_x2, pad_y2), (WIDTH - pad_x2, HEIGHT - pad_y2)], fill=inner)
    _frame(draw)
    return img


def _diagonal_stripes(c1: tuple[int, int, int], c2: tuple[int, int, int], n_stripes: int = 6) -> Image.Image:
    """Slanted stripes from top-left to bottom-right."""
    img, draw = _new()
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=c1)
    # Reach corner-to-corner using stripe step along the main diagonal.
    step = (WIDTH + HEIGHT) // n_stripes
    for i in range(n_stripes):
        if i % 2 == 0:
            continue
        offset = i * step - HEIGHT
        draw.polygon(
            [
                (offset, HEIGHT),
                (offset + step, HEIGHT),
                (offset + step + HEIGHT, 0),
                (offset + HEIGHT, 0),
            ],
            fill=c2,
        )
    _frame(draw)
    return img


def _swallow_tail(left: tuple[int, int, int], right: tuple[int, int, int]) -> Image.Image:
    """Alpha (A) — left half white, right half blue, with V notch cut on the fly side."""
    img, draw = _new()
    notch = WIDTH // 5
    body_right = WIDTH - notch
    # left half
    draw.rectangle([(0, 0), (WIDTH // 2, HEIGHT)], fill=left)
    # right half (only as far as body_right)
    draw.rectangle([(WIDTH // 2, 0), (body_right, HEIGHT)], fill=right)
    # Top and bottom triangles forming the swallowtail prongs
    draw.polygon(
        [(body_right, 0), (WIDTH, 0), (body_right, HEIGHT // 2)],
        fill=right,
    )
    draw.polygon(
        [(body_right, HEIGHT), (WIDTH, HEIGHT), (body_right, HEIGHT // 2)],
        fill=right,
    )
    # Frame around the whole swallowtail shape
    draw.line([(0, 0), (WIDTH - 1, 0)], fill=BLACK, width=BORDER)
    draw.line([(0, HEIGHT - 1), (WIDTH - 1, HEIGHT - 1)], fill=BLACK, width=BORDER)
    draw.line([(0, 0), (0, HEIGHT - 1)], fill=BLACK, width=BORDER)
    draw.line([(WIDTH - 1, 0), (body_right, HEIGHT // 2)], fill=BLACK, width=BORDER)
    draw.line([(WIDTH - 1, HEIGHT - 1), (body_right, HEIGHT // 2)], fill=BLACK, width=BORDER)
    return img


def _pennant(color: tuple[int, int, int]) -> Image.Image:
    """Bravo (B) — a long red triangular pennant. We mask the rectangle as a triangle."""
    img, draw = _new()
    # Triangle from hoist (full height) tapering to point at fly mid-height.
    draw.polygon(
        [(0, 0), (WIDTH, HEIGHT // 2), (0, HEIGHT)],
        fill=color,
    )
    # outline
    draw.polygon(
        [(0, 0), (WIDTH, HEIGHT // 2), (0, HEIGHT)],
        outline=BLACK,
        width=BORDER,
    )
    return img


def _four_triangles(top: tuple[int, int, int], right: tuple[int, int, int], bottom: tuple[int, int, int], left: tuple[int, int, int]) -> Image.Image:
    """Zulu (Z) — 4 triangles meeting at center via the two diagonals."""
    img, draw = _new()
    cx, cy = WIDTH // 2, HEIGHT // 2
    draw.polygon([(0, 0), (WIDTH, 0), (cx, cy)], fill=top)
    draw.polygon([(WIDTH, 0), (WIDTH, HEIGHT), (cx, cy)], fill=right)
    draw.polygon([(WIDTH, HEIGHT), (0, HEIGHT), (cx, cy)], fill=bottom)
    draw.polygon([(0, HEIGHT), (0, 0), (cx, cy)], fill=left)
    _frame(draw)
    return img


# Per-letter renderers. Designs follow the МСС-65 international code of signals.
_BUILDERS: dict[str, Callable[[], Image.Image]] = {
    "A": lambda: _swallow_tail(WHITE, BLUE),
    "B": lambda: _pennant(RED),
    "C": lambda: _horizontal_stripes([BLUE, WHITE, RED, WHITE, BLUE]),
    "D": lambda: _horizontal_stripes([YELLOW, BLUE, YELLOW], weights=[1, 2, 1]),
    "E": lambda: _horizontal_stripes([BLUE, RED]),
    "F": lambda: _diamond_on(WHITE, RED),
    "G": lambda: _vertical_stripes([YELLOW, BLUE, YELLOW, BLUE, YELLOW, BLUE]),
    "H": lambda: _vertical_stripes([WHITE, RED]),
    "I": lambda: _circle_on(YELLOW, BLACK),
    "J": lambda: _horizontal_stripes([BLUE, WHITE, BLUE]),
    "K": lambda: _vertical_stripes([YELLOW, BLUE]),
    "L": lambda: _quartered(YELLOW, BLACK, BLACK, YELLOW),
    "M": lambda: _saltire(BLUE, WHITE),
    "N": lambda: _checkerboard(4, 4, WHITE, BLUE),
    "O": lambda: _diagonal_split(RED, YELLOW),
    "P": lambda: _square_on(BLUE, WHITE),
    "Q": lambda: _solid(YELLOW),
    "R": lambda: _cross(RED, YELLOW),
    "S": lambda: _square_on(WHITE, BLUE),
    "T": lambda: _vertical_stripes([RED, WHITE, BLUE]),
    "U": lambda: _quartered(WHITE, RED, RED, WHITE),
    "V": lambda: _saltire(WHITE, RED),
    "W": lambda: _concentric_rects(BLUE, WHITE, RED),
    "X": lambda: _cross(WHITE, BLUE),
    "Y": lambda: _diagonal_stripes(YELLOW, RED, n_stripes=6),
    "Z": lambda: _four_triangles(YELLOW, BLACK, RED, BLUE),
}


def render(code: str) -> Path:
    """Render the flag for `code` and return the cached file path."""
    settings.flags_dir.mkdir(parents=True, exist_ok=True)
    path = settings.flags_dir / f"{code}.png"
    if path.exists():
        return path
    builder = _BUILDERS.get(code)
    if builder is None:
        raise KeyError(f"no flag renderer for {code!r}")
    img = builder()
    img.save(path, format="PNG", optimize=True)
    return path


def render_letter_card(code: str) -> Path:
    """Render a plain card showing just the letter (for letter-recognition prompts)."""
    return render_text_card(code)


# Bump whenever render_text_card() output changes — old card_v{N}_*.png on
# bind-mounted ./assets/ are then orphaned (never re-served) and the new
# version gets generated fresh on next access. Avoids the «I deployed a fix
# but the cached file is still the old buggy render» trap.
_CARD_RENDERER_VERSION = 2


def render_text_card(text: str) -> Path:
    """Render a 600×400 card with `text` centered, auto-sized to fit.

    Iteratively shrinks the font and re-wraps until the rendered text fits
    inside an inner padded box — guarantees no clipping at the edges for any
    realistic question prompt (single Morse character or full signal meaning).

    Used by text-only trainers (Morse, names, meanings) so every quiz message
    is a photo — that's what lets us `edit_media` between question and result
    instead of sending a new message each turn.
    """
    import hashlib
    import textwrap

    settings.flags_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    path = settings.flags_dir / f"card_v{_CARD_RENDERER_VERSION}_{key}.png"
    if path.exists():
        return path

    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], outline=BLACK, width=BORDER)

    # Safe inner box — everything must fit here.
    pad = 36
    inner_w = WIDTH - 2 * pad
    inner_h = HEIGHT - 2 * pad

    bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    regular_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    length = len(text)
    # Bold for short labels (single letter / morse / short word) — easier to
    # spot. Regular for longer free text — more comfortable to read wrapped.
    font_path = bold_path if length <= 16 else regular_path

    # Length-driven starting size; iterative shrink below handles overruns.
    if length <= 3:
        size = 220
    elif length <= 7:
        size = 140
    elif length <= 16:
        size = 80
    elif length <= 32:
        size = 50
    else:
        size = 36
    min_size = 14

    def _try(size: int) -> tuple[ImageFont.FreeTypeFont, str, int, int]:
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            font = ImageFont.load_default()
        # Real font metric — width of a representative Cyrillic sample.
        sample = "Мабвгдеёжзи"
        avg_char_w = max(1.0, font.getlength(sample) / len(sample))
        chars_per_line = max(6, int(inner_w / avg_char_w))
        wrapped = (
            textwrap.fill(text, width=chars_per_line, break_long_words=False)
            if length > chars_per_line
            else text
        )
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=size // 10)
        return font, wrapped, bbox[2] - bbox[0], bbox[3] - bbox[1]

    font, wrapped, tw, th = _try(size)
    while (tw > inner_w or th > inner_h) and size > min_size:
        size = max(min_size, int(size * 0.85))
        font, wrapped, tw, th = _try(size)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=size // 10)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (WIDTH - tw) // 2 - bbox[0]
    y = (HEIGHT - th) // 2 - bbox[1]
    draw.multiline_text(
        (x, y), wrapped, fill=BLACK, font=font, align="center", spacing=size // 10
    )

    img.save(path, format="PNG", optimize=True)
    return path


def _cleanup_stale_text_cards() -> None:
    """Remove text cards from previous renderer versions.

    Cards are content-addressed by hash + a version prefix; bumping the
    version produces files under a fresh name. Old ones become dead weight,
    so drop them on startup to keep the flags dir lean.
    """
    if not settings.flags_dir.is_dir():
        return
    keep_prefix = f"card_v{_CARD_RENDERER_VERSION}_"
    for f in settings.flags_dir.glob("card_*.png"):
        if not f.name.startswith(keep_prefix):
            try:
                f.unlink()
            except OSError:
                pass


def prerender_all() -> None:
    """Render the full alphabet up-front so the first quiz is snappy."""
    from app.training.mcs65.data import all_codes

    _cleanup_stale_text_cards()
    for code in all_codes():
        render(code)
        render_letter_card(code)


def compose_numbered_grid(image_paths: list[Path]) -> bytes:
    """Compose 4 images into a 2×2 numbered grid, return PNG bytes.

    Used by trainers that ask the user to pick visually from several flags —
    each cell gets a 1–4 badge so the inline keyboard can carry numeric labels.
    Generated fresh per question (cheap with Pillow), no on-disk cache: order
    is randomised per call so caching by permutation would be wasteful.
    """
    if len(image_paths) != 4:
        raise ValueError(f"compose_numbered_grid expects 4 images, got {len(image_paths)}")

    tile_w, tile_h = 360, 240
    pad = 18
    grid_w = 2 * tile_w + 3 * pad
    grid_h = 2 * tile_h + 3 * pad
    grid = Image.new("RGB", (grid_w, grid_h), (235, 235, 235))
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except OSError:
        font = ImageFont.load_default()

    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    for i, (col, row) in enumerate(positions):
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + pad)
        tile = Image.open(image_paths[i]).convert("RGB").resize((tile_w, tile_h))
        grid.paste(tile, (x, y))
        badge_d = 48
        bx, by = x + 8, y + 8
        draw.ellipse([(bx, by), (bx + badge_d, by + badge_d)], fill=BLACK)
        num = str(i + 1)
        bbox = draw.textbbox((0, 0), num, font=font)
        tw_text = bbox[2] - bbox[0]
        th_text = bbox[3] - bbox[1]
        draw.text(
            (bx + (badge_d - tw_text) // 2 - bbox[0], by + (badge_d - th_text) // 2 - bbox[1]),
            num,
            fill=WHITE,
            font=font,
        )

    import io

    buf = io.BytesIO()
    grid.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
