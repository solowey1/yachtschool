"""Tiny aiohttp server that exposes pre-rendered flag PNGs.

Telegram's inline mode needs either a `file_id` for an already-uploaded
photo or a publicly-reachable HTTPS URL. This server is the URL path:
nginx on the host proxies `/flags/*` to us, we serve from the local
flags cache. No spam, no /preload_inline needed.
"""

from __future__ import annotations

from aiohttp import web

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


async def _health(_: web.Request) -> web.Response:
    return web.Response(text="ok\n")


async def _serve_flag(request: web.Request) -> web.FileResponse:
    """Serve one PNG from settings.flags_dir.

    Path-traversal guarded: only plain filenames matching <safe>.png are
    allowed; no slashes, no «..».
    """
    filename = request.match_info["filename"]
    if (
        not filename
        or "/" in filename
        or ".." in filename
        or not filename.endswith(".png")
    ):
        raise web.HTTPNotFound()
    path = settings.flags_dir / filename
    if not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(
        path,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Type": "image/png",
        },
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", _health)
    app.router.add_get("/flags/{filename}", _serve_flag)
    return app


async def start(host: str = "0.0.0.0", port: int | None = None) -> web.AppRunner:
    runner = web.AppRunner(build_app(), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port or settings.web_port)
    await site.start()
    logger.info("http.listening", host=host, port=port or settings.web_port)
    return runner
