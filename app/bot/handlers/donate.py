"""Donate flow — Telegram Stars (XTR currency).

Stars don't go through a payment provider, so `provider_token` is left
empty and `currency` is "XTR". The amount in LabeledPrice is the Stars
count directly (no x100 scaling like with normal fiat currencies).

Flow:
  1. User taps «💛 Поддержать» → donate page with 5 amount buttons
  2. User picks an amount → bot.send_invoice (separate chat message
     with the Stars payment button)
  3. Telegram fires PreCheckoutQuery → answer ok=True
  4. Telegram fires Message.successful_payment → thank the user
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import DonateCB, NavCB
from app.bot.keyboards import donate_menu, main_menu
from app.db.models import User
from app.i18n import t
from app.logger import get_logger

router = Router(name="donate")
logger = get_logger(__name__)


async def _show_donate_page(cq: CallbackQuery, lang: str) -> None:
    if cq.message is None:
        return
    text = t("donate.page_text", lang)
    keyboard = donate_menu(lang)
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


@router.callback_query(NavCB.filter((F.target == "donate") & (F.subject.is_(None))))
async def open_donate(cq: CallbackQuery, lang: str) -> None:
    await _show_donate_page(cq, lang)
    await cq.answer()


@router.callback_query(DonateCB.filter())
async def on_donate_amount(
    cq: CallbackQuery, callback_data: DonateCB, lang: str
) -> None:
    """Send a Stars invoice. The donate page stays; the invoice arrives as a
    separate chat message so user can compare amounts before deciding.
    """
    amount = max(1, int(callback_data.amount))
    title = t("donate.invoice_title", lang)
    description = t("donate.invoice_description", lang, amount=amount)
    payload = f"donate_{amount}_{cq.from_user.id}"

    try:
        await cq.bot.send_invoice(
            chat_id=cq.from_user.id,
            title=title,
            description=description,
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=f"⭐ × {amount}", amount=amount)],
            # provider_token left empty — required for Stars.
            provider_token="",
        )
        await cq.answer()
    except Exception as exc:  # noqa: BLE001
        logger.exception("donate.invoice_failed", amount=amount, error=str(exc))
        await cq.answer(t("common.error", lang), show_alert=True)


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    """Always approve — Stars donations have no inventory or fraud check."""
    try:
        await query.answer(ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("donate.pre_checkout_failed", error=str(exc))


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message, session: AsyncSession, user: User, lang: str
) -> None:
    payment = message.successful_payment
    amount = payment.total_amount if payment else 0
    payload = payment.invoice_payload if payment else ""
    logger.info(
        "payment.received",
        user_id=message.from_user.id if message.from_user else None,
        amount=amount,
        payload=payload,
        currency=payment.currency if payment else None,
    )

    # Detailed-stats purchase unlocks a per-user entitlement; anything else is
    # treated as a plain donation.
    if payload == "detailed_stats":
        if user is not None:
            user.detailed_stats_unlocked = True
            await session.flush()
        await message.answer(t("stats.bought", lang), reply_markup=main_menu(lang))
        return

    await message.answer(
        t("donate.thanks", lang, amount=amount),
        reply_markup=main_menu(lang),
    )
