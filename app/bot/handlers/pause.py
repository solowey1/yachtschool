"""Pause daily-delivery flow.

Two entry points share the same duration picker:
  • the «⏸ Сделать паузу» button under the daily-batch header
  • the «⏸ Пауза» row inside Settings

Both let the user pick 1/3/7/14/30 days or «Навсегда». The choice
writes `user.paused_until`; the scheduler skips users while that
timestamp is in the future.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import NavCB, PauseCB
from app.bot.keyboards import (
    daily_header_keyboard,
    pause_duration_picker,
    pause_settings_view,
)
from app.db.models import User
from app.i18n import t
from app.services import user_settings

router = Router(name="pause")


def _format_until(dt: datetime, lang: str) -> str:
    dt = dt.astimezone(pytz.UTC)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _pause_status_text(user: User, lang: str) -> str:
    """One-liner describing the current pause state."""
    if not user_settings.is_paused(user):
        return t("pause.status_not_paused", lang)
    if user_settings.is_paused_forever(user):
        return t("pause.status_forever", lang)
    ends = user_settings.pause_ends_at(user)
    return t("pause.status_until", lang, until=_format_until(ends, lang))


# ── From the daily-batch header ──────────────────────────────────────────────

@router.callback_query(PauseCB.filter(F.action == "open_header"))
async def on_header_open(cq: CallbackQuery, lang: str) -> None:
    """User tapped «⏸ Сделать паузу» on the daily header. Edit the header
    into the duration picker so the current header message becomes an
    interactive control instead of a plain notice.
    """
    if cq.message is None:
        await cq.answer()
        return
    try:
        await cq.message.edit_text(
            t("pause.picker_prompt", lang),
            reply_markup=pause_duration_picker(lang, from_header=True),
        )
    except TelegramBadRequest:
        pass
    await cq.answer()


@router.callback_query(PauseCB.filter(F.action == "cancel_hdr"))
async def on_header_cancel(cq: CallbackQuery, lang: str) -> None:
    """Cancel from the header picker → restore the original header text."""
    if cq.message is None:
        await cq.answer()
        return
    try:
        await cq.message.edit_text(
            t("pause.picker_cancelled", lang),
            reply_markup=daily_header_keyboard(lang),
        )
    except TelegramBadRequest:
        pass
    await cq.answer()


# ── From Settings ────────────────────────────────────────────────────────────

@router.callback_query(PauseCB.filter(F.action == "view"))
async def on_settings_view(cq: CallbackQuery, user: User, lang: str) -> None:
    """Pause section inside Settings — shows current status + controls."""
    if cq.message is None:
        await cq.answer()
        return
    body = t("pause.settings_page", lang, status=_pause_status_text(user, lang))
    try:
        await cq.message.edit_text(
            body, reply_markup=pause_settings_view(lang, is_paused=user_settings.is_paused(user))
        )
    except TelegramBadRequest:
        await cq.message.answer(
            body, reply_markup=pause_settings_view(lang, is_paused=user_settings.is_paused(user))
        )
    await cq.answer()


@router.callback_query(PauseCB.filter(F.action == "unpause"))
async def on_unpause(
    cq: CallbackQuery, session: AsyncSession, user: User, lang: str
) -> None:
    user_settings.unpause(user)
    await session.flush()
    body = t("pause.settings_page", lang, status=_pause_status_text(user, lang))
    if cq.message is not None:
        try:
            await cq.message.edit_text(
                body, reply_markup=pause_settings_view(lang, is_paused=False)
            )
        except TelegramBadRequest:
            pass
    await cq.answer(t("pause.resumed", lang))


# ── Duration selection (shared by both entry points) ─────────────────────────

@router.callback_query(PauseCB.filter(F.action == "pick"))
async def on_pick(
    cq: CallbackQuery,
    callback_data: PauseCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    days = int(callback_data.days)
    user_settings.set_pause(user, days)
    await session.flush()

    if days <= 0:
        message = t("pause.confirmed_forever", lang)
    else:
        ends = user_settings.pause_ends_at(user)
        message = t(
            "pause.confirmed_until",
            lang,
            days=days,
            until=_format_until(ends, lang) if ends else "",
        )

    if cq.message is None:
        await cq.answer(t("pause.short_confirm", lang))
        return
    # Same message becomes the confirmation, with a «В главное меню» button
    # so the user has an obvious way out.
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("menu.back_to_main", lang),
                    callback_data=NavCB(target="main").pack(),
                )
            ]
        ]
    )
    try:
        await cq.message.edit_text(message, reply_markup=keyboard)
    except TelegramBadRequest:
        await cq.message.answer(message, reply_markup=keyboard)
    await cq.answer(t("pause.short_confirm", lang))
