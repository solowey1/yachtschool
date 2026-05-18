"""Telegram `file_id` cache for inline-mode photo results.

Inline mode rejects local files; it needs either a public URL or a file_id
the bot has already uploaded. `/preload_inline` sends every flag and
pennant to the caller's DM once and stores the resulting file_id here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InlineMediaCache
from app.logger import get_logger
from app.services.inline_search import all_codes
from app.training.mcs65 import flag_renderer, pennant_renderer

logger = get_logger(__name__)


def image_path_for(code: str) -> Path:
    """Render-or-fetch the cached PNG for `code`, returning its filesystem path."""
    if len(code) == 1 and code.isalpha():
        return flag_renderer.render(code)
    return pennant_renderer.render(code)


async def get_file_ids(session: AsyncSession, codes: list[str]) -> dict[str, str]:
    res = await session.execute(
        select(InlineMediaCache.code, InlineMediaCache.file_id).where(
            InlineMediaCache.code.in_(codes)
        )
    )
    return {row.code: row.file_id for row in res.all()}


async def set_file_id(session: AsyncSession, code: str, file_id: str) -> None:
    stmt = (
        pg_insert(InlineMediaCache)
        .values(code=code, file_id=file_id)
        .on_conflict_do_update(
            index_elements=["code"], set_={"file_id": file_id}
        )
    )
    await session.execute(stmt)


async def cached_codes(session: AsyncSession) -> set[str]:
    res = await session.execute(select(InlineMediaCache.code))
    return {row[0] for row in res.all()}


async def preload(
    bot: Bot, chat_id: int, session: AsyncSession, *, only_missing: bool = True
) -> int:
    """Send every flag/pennant to `chat_id` and persist Telegram's file_id.

    Returns the number of new entries written. Skips codes already cached
    when `only_missing` is True (default).
    """
    target_codes = all_codes()
    if only_missing:
        existing = await cached_codes(session)
        target_codes = [c for c in target_codes if c not in existing]

    written = 0
    for code in target_codes:
        try:
            sent = await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(str(image_path_for(code))),
            )
            file_id = sent.photo[-1].file_id  # largest size
            await set_file_id(session, code, file_id)
            written += 1
            # Telegram caps photo bursts; be polite.
            await asyncio.sleep(0.1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("inline.preload_failed", code=code, error=str(exc))
    return written
