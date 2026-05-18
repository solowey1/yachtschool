from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from app.bot.setup import build_bot, build_dispatcher
from app.db.session import engine
from app.logger import configure_logging, get_logger
from app.services.scheduler import start_scheduler
from app.training.mcs65 import flag_renderer, pennant_renderer
from app.training.mcs65 import trainers as mcs65_trainers


def _run_migrations() -> None:
    cfg = AlembicConfig(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "alembic"))
    command.upgrade(cfg, "head")


async def _async_main() -> None:
    logger = get_logger("main")
    bot = build_bot()
    dp = build_dispatcher()

    scheduler = start_scheduler(bot)
    logger.info("bot.starting")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    configure_logging()
    mcs65_trainers.register()
    flag_renderer.prerender_all()
    pennant_renderer.prerender_all()
    # Alembic spins up its own async engine internally — run it before our event loop starts.
    _run_migrations()
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
