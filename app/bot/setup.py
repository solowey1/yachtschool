from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router as root_router
from app.bot.middlewares import DbAndUserMiddleware
from app.config import settings


def build_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    middleware = DbAndUserMiddleware()
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    dp.inline_query.middleware(middleware)
    dp.include_router(root_router)
    return dp
