"""Inline mode — search МСС flags/pennants from any chat via @bot <query>."""

from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.i18n import t
from app.services import inline_cache, inline_search
from app.training.mcs65 import data, pennants

router = Router(name="inline")

INLINE_RESULTS_LIMIT = 50  # Telegram's hard cap per answer()
CACHE_TIME_SECONDS = 60


def _meta(code: str, lang: str) -> tuple[str, str, str]:
    """Return (title, description, caption) for inline result of `code`.

    title goes above the row in Telegram's picker, description below it,
    caption is what ends up under the photo when the user picks the result.
    """
    if len(code) == 1 and code.isalpha():
        ru_name = t(f"mcs65.name.{code}", lang)
        en_name = data.NATO_PHONETIC_EN.get(code, "")
        meaning = t(f"mcs65.meaning.{code}", lang)
        morse = data.get(code).morse
        title = f"🚩 {code} — {ru_name} ({en_name})"
        description = meaning
        caption = (
            f"<b>{code} — {ru_name}</b> ({en_name})\n"
            f"📡 Морзе: <code>{morse}</code>\n\n"
            f"<i>{meaning}</i>"
        )
        return title, description, caption

    if code.startswith("N"):
        p = pennants.get(code)
        ru_name = t(f"mcs65.pennant_name.{code}", lang)
        en_name = pennants.PHONETIC_EN.get(code, "")
        title = f"🎏 {p.short_label} — {ru_name} ({en_name})"
        description = t(f"mcs65.pennant_meaning.{code}", lang)
        caption = (
            f"<b>Цифровой пенант «{p.short_label}»</b>\n"
            f"📛 {ru_name} ({en_name})\n"
            f"📡 Морзе: <code>{p.morse or '—'}</code>"
        )
        return title, description, caption

    # Substitutes + answering pennant
    ru_name = t(f"mcs65.pennant_name.{code}", lang)
    en_name = pennants.PHONETIC_EN.get(code, "")
    description = t(f"mcs65.pennant_meaning.{code}", lang)
    icon = "📣" if code == "AP" else "🔁"
    title = f"{icon} {ru_name} ({en_name})"
    caption = f"<b>{ru_name}</b> ({en_name})\n\n<i>{description}</i>"
    return title, description, caption


@router.inline_query()
async def on_inline_query(
    query: InlineQuery, session: AsyncSession, lang: str
) -> None:
    codes = inline_search.search(query.query, lang)[:INLINE_RESULTS_LIMIT]
    file_ids = await inline_cache.get_file_ids(session, codes)

    results: list = []
    for code in codes:
        title, description, caption = _meta(code, lang)
        if code in file_ids:
            results.append(
                InlineQueryResultCachedPhoto(
                    id=code,
                    photo_file_id=file_ids[code],
                    title=title,
                    description=description,
                    caption=caption,
                    parse_mode="HTML",
                )
            )
        else:
            # Fallback — until /preload_inline runs, send a text card.
            results.append(
                InlineQueryResultArticle(
                    id=code,
                    title=title,
                    description=description,
                    input_message_content=InputTextMessageContent(
                        message_text=caption, parse_mode="HTML"
                    ),
                )
            )

    await query.answer(
        results, cache_time=CACHE_TIME_SECONDS, is_personal=False
    )


@router.message(Command("preload_inline"))
async def cmd_preload_inline(
    message: Message, session: AsyncSession, lang: str
) -> None:
    """Bootstrap the file_id cache. Sends all 40 flags to the caller's DM once.

    Idempotent: codes already cached are skipped. Restricted to private chats
    so it never accidentally floods a group.
    """
    if message.chat.type != ChatType.PRIVATE:
        return

    await message.answer(t("inline.preload_start", lang))
    written = await inline_cache.preload(message.bot, message.chat.id, session)
    if written == 0:
        await message.answer(t("inline.preload_already_done", lang))
    else:
        await message.answer(t("inline.preload_done", lang, count=written))
