from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import TopicCB
from app.i18n import t
from app.training.registry import registry


def main_menu(lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for topic in registry.topics():
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(topic.title_i18n_key, lang),
                    callback_data=TopicCB(subject=topic.subject, topic=topic.code).pack(),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text=t("menu.stats_button", lang), callback_data="stats:open")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
