from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import NavCB, SettingsCB
from app.bot.keyboards import (
    settings_count_picker,
    settings_lang_picker,
    settings_root,
    settings_time_picker,
)
from app.db.models import User
from app.i18n import t, translator
from app.services import user_settings

router = Router(name="settings")


def _lang_label(user: User, lang: str) -> str:
    return t(f"settings.lang_name.{user.language}", lang) or user.language.upper()


def _settings_root_text(user: User, lang: str) -> str:
    count_value = user_settings.effective_count(user)
    count_suffix = "" if user_settings.is_count_overridden(user) else t("settings.suffix_default", lang)
    time_value = user_settings.effective_time_utc(user)
    time_suffix = "" if user_settings.is_time_overridden(user) else t("settings.suffix_default", lang)
    return t(
        "settings.title",
        lang,
        lang_label=_lang_label(user, lang),
        count_value=count_value,
        count_suffix=count_suffix,
        time_value=time_value,
        time_suffix=time_suffix,
        default_time=user_settings.env_default_time_str(),
        default_tz=user_settings.env_default_timezone(),
        default_count=user_settings.env_default_count(),
    )


async def _swap(cq: CallbackQuery, text: str, keyboard) -> None:
    """Edit-or-resend the current text message (settings pages are text-only)."""
    if cq.message is None:
        return
    if cq.message.photo:
        try:
            await cq.message.delete()
        except TelegramBadRequest:
            pass
        await cq.message.answer(text, reply_markup=keyboard)
        return
    try:
        await cq.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await cq.message.answer(text, reply_markup=keyboard)


def _has_multiple_languages() -> bool:
    return len(translator().available_languages()) > 1


@router.callback_query(NavCB.filter(F.target == "settings"))
async def open_settings(cq: CallbackQuery, user: User, lang: str) -> None:
    await _swap(
        cq,
        _settings_root_text(user, lang),
        settings_root(lang, language_pickable=_has_multiple_languages()),
    )
    await cq.answer()


@router.callback_query(SettingsCB.filter(F.action == "view"))
async def view_settings_subpage(
    cq: CallbackQuery, callback_data: SettingsCB, user: User, lang: str
) -> None:
    field = callback_data.field
    if field == "lang" and _has_multiple_languages():
        await _swap(cq, t("settings.choose_lang", lang), settings_lang_picker(lang))
    elif field == "count":
        await _swap(
            cq,
            t("settings.choose_count", lang, current=user_settings.effective_count(user)),
            settings_count_picker(lang),
        )
    elif field == "time":
        await _swap(
            cq,
            t("settings.choose_time", lang, current=user_settings.effective_time_utc(user)),
            settings_time_picker(lang),
        )
    else:
        await _swap(
            cq,
            _settings_root_text(user, lang),
            settings_root(lang, language_pickable=_has_multiple_languages()),
        )
    await cq.answer()


@router.callback_query(SettingsCB.filter(F.action == "set"))
async def apply_setting(
    cq: CallbackQuery,
    callback_data: SettingsCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    field, value = callback_data.field, callback_data.value
    if field == "lang":
        if value in translator().available_languages():
            user.language = value
            lang = value  # render the success page in the newly-chosen language
    elif field == "count":
        try:
            user.daily_questions_count = max(1, min(50, int(value)))
        except ValueError:
            pass
    elif field == "time" and len(value) == 4 and value.isdigit():
        user.delivery_time_utc = f"{value[:2]}:{value[2:]}"
    await session.flush()

    await _swap(
        cq,
        _settings_root_text(user, lang),
        settings_root(lang, language_pickable=_has_multiple_languages()),
    )
    await cq.answer(t("settings.updated", lang))


@router.callback_query(SettingsCB.filter(F.action == "reset"))
async def reset_setting(
    cq: CallbackQuery,
    callback_data: SettingsCB,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    if callback_data.field == "count":
        user.daily_questions_count = None
    elif callback_data.field == "time":
        user.delivery_time_utc = None
    await session.flush()

    await _swap(
        cq,
        _settings_root_text(user, lang),
        settings_root(lang, language_pickable=_has_multiple_languages()),
    )
    await cq.answer(t("settings.updated", lang))
