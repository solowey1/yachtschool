"""Tiny aiohttp server that exposes pre-rendered flag PNGs.

Telegram's inline mode needs either a `file_id` for an already-uploaded
photo or a publicly-reachable HTTPS URL. This server is the URL path:
nginx on the host proxies `/flags/*` to us, we serve from the local
flags cache. No spam, no /preload_inline needed.

Two routes:
* `/flags/{name}.png` — full 600×400 image (used as link-preview source)
* `/flags/thumb/{name}.png` — 192×128 thumbnail (used as Article picker thumb)
  so Telegram clients render the inline picker as a compact list, not a
  grid of full photos. Thumbs are generated on first request and cached.
"""

from __future__ import annotations

from PIL import Image
from aiohttp import web

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

THUMB_W, THUMB_H = 192, 128


def _safe_filename(filename: str) -> bool:
    return bool(filename) and "/" not in filename and ".." not in filename and filename.endswith(".png")


async def _health(_: web.Request) -> web.Response:
    return web.Response(text="ok\n")


async def _serve_flag(request: web.Request) -> web.FileResponse:
    filename = request.match_info["filename"]
    if not _safe_filename(filename):
        raise web.HTTPNotFound()
    path = settings.flags_dir / filename
    if not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=86400", "Content-Type": "image/png"},
    )


async def _serve_flag_thumb(request: web.Request) -> web.FileResponse:
    """Serve a small thumbnail of the source flag. Generated and cached on demand."""
    filename = request.match_info["filename"]
    if not _safe_filename(filename):
        raise web.HTTPNotFound()
    source = settings.flags_dir / filename
    if not source.is_file():
        raise web.HTTPNotFound()
    thumb = settings.flags_dir / f"_thumb_{filename}"
    if not thumb.is_file() or thumb.stat().st_mtime < source.stat().st_mtime:
        with Image.open(source) as img:
            img = img.convert("RGB")
            img.thumbnail((THUMB_W, THUMB_H))
            img.save(thumb, format="PNG", optimize=True)
    return web.FileResponse(
        thumb,
        headers={"Cache-Control": "public, max-age=86400", "Content-Type": "image/png"},
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", _health)
    # thumb route must come first — aiohttp matches in registration order.
    app.router.add_get("/flags/thumb/{filename}", _serve_flag_thumb)
    app.router.add_get("/flags/{filename}", _serve_flag)
    return app


async def start(host: str = "0.0.0.0", port: int | None = None) -> web.AppRunner:
    runner = web.AppRunner(build_app(), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port or settings.web_port)
    await site.start()
    logger.info("http.listening", host=host, port=port or settings.web_port)
    return runner
