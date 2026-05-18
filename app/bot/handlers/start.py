from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import main_menu
from app.i18n import t
from app.logger import get_logger
from app.services import inline_cache, inline_search, user_settings

router = Router(name="start")
logger = get_logger(__name__)


async def _bootstrap_inline_if_needed(message: Message, session: AsyncSession, lang: str) -> None:
    """First /start in a private chat seeds the inline-mode file_id cache.

    Without this, inline picks fall back to text-only «article» results
    (emoji-on-white thumbnails, no photo when picked). Telegram's API offers
    no way around that — inline photo results need either a public URL or a
    file_id, so we generate file_ids by sending each flag to the first user
    who runs /start. Subsequent users skip this branch — the cache is global.
    Wrapped in a try/except so a late HTML or messaging failure doesn't
    poison the rest of the /start flow.
    """
    if message.chat.type != ChatType.PRIVATE:
        return
    try:
        expected = set(inline_search.all_codes())
        cached = await inline_cache.cached_codes(session)
        if cached.issuperset(expected):
            return

        try:
            await message.answer(t("inline.bootstrap_notice", lang))
        except Exception as exc:  # noqa: BLE001
            logger.warning("inline.bootstrap_notice_failed", error=str(exc))

        written = await inline_cache.preload(message.bot, message.chat.id, session)
        logger.info("inline.bootstrap_done", written=written)
        if written > 0:
            try:
                await message.answer(t("inline.bootstrap_done", lang))
            except Exception as exc:  # noqa: BLE001
                logger.warning("inline.bootstrap_done_msg_failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("inline.bootstrap_failed", error=str(exc))


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, lang: str) -> None:
    name = (message.from_user.first_name if message.from_user else None) or t(
        "start.name_fallback", lang
    )
    await message.answer(
        t(
            "start.welcome",
            lang,
            name=name,
            time=user_settings.env_default_time_str(),
            tz=user_settings.env_default_timezone(),
            count=user_settings.env_default_count(),
        ),
        reply_markup=main_menu(lang),
    )
    await _bootstrap_inline_if_needed(message, session, lang)


@router.message(Command("menu"))
async def cmd_menu(message: Message, lang: str) -> None:
    await message.answer(t("menu.main_title", lang), reply_markup=main_menu(lang))
