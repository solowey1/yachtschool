from __future__ import annotations

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.bot.handlers import router as root_router
from app.bot.middlewares import DbAndUserMiddleware
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


def build_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def _build_error_router() -> Router:
    """Catch failures aiogram raises before our handler-level try/except sees them.

    Mostly ValidationError from CallbackData unpack — those happen during
    router matching, before middleware runs. Without this, the user sees
    «вечная загрузка» and the operator sees nothing in the logs.
    """
    r = Router(name="errors")

    @r.errors()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception(
            "dispatcher.error",
            update_id=getattr(event.update, "update_id", None),
            error=str(event.exception),
            exc_type=type(event.exception).__name__,
        )
        # Returning True tells aiogram we've handled it (no further propagation).
        return True

    return r


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    middleware = DbAndUserMiddleware()
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    dp.inline_query.middleware(middleware)
    dp.include_router(_build_error_router())
    dp.include_router(root_router)
    return dp
