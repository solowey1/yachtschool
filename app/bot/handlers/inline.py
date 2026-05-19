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
    LinkPreviewOptions,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.i18n import t
from app.services import inline_cache, inline_search
from app.training.mcs65 import data, pennants

router = Router(name="inline")

INLINE_RESULTS_LIMIT = 50  # Telegram's hard cap per answer()
# 0 = no Telegram-side caching. Inline result types change occasionally during
# tuning, and an aggressively cached old layout sticks around for clients even
# after a redeploy. Cheap to regenerate per query for our scale (<1ms).
CACHE_TIME_SECONDS = 0
# Source image dimensions (used by link-preview, which renders the full photo).
PHOTO_WIDTH = 600
PHOTO_HEIGHT = 400
# Picker thumbnail — kept deliberately small so Telegram clients render the
# inline picker as a compact Article list instead of a photo-card grid.
# The web server resizes the source PNG to these dimensions on demand.
THUMB_WIDTH = 192
THUMB_HEIGHT = 128


def _filename_for(code: str) -> str:
    return f"{code}.png" if len(code) == 1 and code.isalpha() else f"pennant_{code}.png"


def _photo_url(code: str) -> str | None:
    """Full-size URL — used by LinkPreviewOptions to render a big preview in chat."""
    base = settings.inline_public_base_url
    if not base:
        return None
    return f"{base.rstrip('/')}/flags/{_filename_for(code)}"


def _thumb_url(code: str) -> str | None:
    """Compact-thumbnail URL — used by the inline picker."""
    base = settings.inline_public_base_url
    if not base:
        return None
    return f"{base.rstrip('/')}/flags/thumb/{_filename_for(code)}"


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
    # file_id cache is only consulted when no public URL is configured —
    # URLs are simpler (no bootstrap, no 40-photo spam) and Telegram
    # downloads the photo straight from there.
    file_ids = (
        {} if settings.inline_public_base_url else await inline_cache.get_file_ids(session, codes)
    )

    results: list = []
    for code in codes:
        title, description, caption = _meta(code, lang)
        url = _photo_url(code)
        thumb = _thumb_url(code)
        if url is not None:
            # Article style in the picker (compact list with small thumbnail +
            # title + description), but the sent message renders a large image
            # preview via LinkPreviewOptions(url=…, prefer_large_media=True,
            # show_above_text=True). Two separate URLs so Telegram clients see
            # «small thumb → compact list» in the picker, not a photo grid.
            results.append(
                InlineQueryResultArticle(
                    id=code,
                    title=title,
                    description=description,
                    thumbnail_url=thumb,
                    thumbnail_width=THUMB_WIDTH,
                    thumbnail_height=THUMB_HEIGHT,
                    input_message_content=InputTextMessageContent(
                        message_text=caption,
                        parse_mode="HTML",
                        link_preview_options=LinkPreviewOptions(
                            url=url,
                            prefer_large_media=True,
                            show_above_text=True,
                        ),
                    ),
                )
            )
        elif code in file_ids:
            # Legacy fallback when only file_id cache is available — Cached
            # photo result natively delivers photo+caption, but picker still
            # shows photos rather than article-style entries.
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
            # Last-resort fallback — no URL, no file_id. Picker shows the
            # default letter-on-white thumb but at least the metadata is right.
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
