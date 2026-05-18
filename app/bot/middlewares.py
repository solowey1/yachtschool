"""Middleware: opens a DB session per update, upserts the user, exposes both in handler data.

Also performs lightweight per-event logging so the operator can see in the
container logs which callbacks/messages/inline-queries actually reach the
bot — invaluable for debugging «button does nothing» reports.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject, User as TgUser

from app.config import settings
from app.db.models import User
from app.db.session import session_scope
from app.logger import get_logger
from app.repositories import users as users_repo

logger = get_logger(__name__)


def _tg_user(event: TelegramObject) -> TgUser | None:
    if isinstance(event, (Message, CallbackQuery, InlineQuery)):
        return event.from_user
    return None


def _log_event(event: TelegramObject) -> None:
    """One-line trace of every incoming event — keep cheap, INFO-level."""
    user = _tg_user(event)
    uid = user.id if user else None
    if isinstance(event, CallbackQuery):
        logger.info("event.callback", data=event.data, user_id=uid)
    elif isinstance(event, Message):
        text = (event.text or event.caption or "")[:60]
        logger.info("event.message", text=text, user_id=uid, chat_type=event.chat.type)
    elif isinstance(event, InlineQuery):
        logger.info("event.inline", query=event.query[:60], user_id=uid)


class DbAndUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        _log_event(event)
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
            try:
                return await handler(event, data)
            except Exception as exc:  # noqa: BLE001
                # Logged here so the operator sees the failure even if aiogram's
                # default error-logging is muted by structlog reconfiguration.
                logger.exception(
                    "handler.failed",
                    error=str(exc),
                    event_type=type(event).__name__,
                )
                raise
