"""Middleware: opens a DB session per update, upserts the user, exposes both in handler data."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser

from app.config import settings
from app.db.models import User
from app.db.session import session_scope
from app.repositories import users as users_repo


def _tg_user(event: TelegramObject) -> TgUser | None:
    if isinstance(event, Message):
        return event.from_user
    if isinstance(event, CallbackQuery):
        return event.from_user
    return None


class DbAndUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_scope() as session:
            data["session"] = session

            tg_user = _tg_user(event)
            user: User | None = None
            if tg_user is not None:
                user = await users_repo.upsert(
                    session,
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    language=settings.default_language,
                )
            data["user"] = user
            data["lang"] = user.language if user else settings.default_language
            return await handler(event, data)
