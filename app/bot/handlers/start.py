from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.config import settings
from app.i18n import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, lang: str) -> None:
    name = (message.from_user.first_name if message.from_user else None) or t(
        "start.name_fallback", lang
    )
    await message.answer(
        t(
            "start.welcome",
            lang,
            name=name,
            time=settings.daily_delivery_time,
            tz=settings.daily_delivery_timezone,
        ),
        reply_markup=main_menu(lang),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, lang: str) -> None:
    await message.answer(t("menu.title", lang), reply_markup=main_menu(lang))
