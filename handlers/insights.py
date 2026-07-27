"""PugBot Insights — раздел «📊 Аналитика».

Владелец (OWNER_ID / is_owner) видит полный снимок метрик.
Остальные пользователи видят только тизер о будущем обновлении.
Никаких намёков на отдельную панель разработчика.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from keyboards.menu import main_menu
from utils.access import is_project_owner
from services.insights import (
    TEASER_TEXT,
    build_owner_snapshot,
    format_owner_report,
)

router = Router(name="insights")
logger = logging.getLogger(__name__)


def _nav_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="insights_refresh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="insights_to_menu",
                )
            ],
        ]
    )


def _teaser_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="insights_to_menu",
                )
            ],
        ]
    )


async def _show_insights(target: Message, user_id: int) -> None:
    if await is_project_owner(user_id):
        try:
            vm = await build_owner_snapshot()
            text = format_owner_report(vm)
            kb = _nav_keyboard()
        except Exception:
            logger.exception("Ошибка сбора Insights")
            text = (
                "📊 <b>Аналитика</b>\n\n"
                "❌ Не удалось собрать статистику. Попробуйте позже."
            )
            kb = _nav_keyboard()
    else:
        text = TEASER_TEXT
        kb = _teaser_keyboard()

    await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "📊 Аналитика")
async def open_insights(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await _show_insights(message, message.from_user.id)


@router.callback_query(F.data == "insights_refresh")
async def insights_refresh(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    if not await is_project_owner(callback.from_user.id):
        await callback.message.edit_text(
            TEASER_TEXT,
            parse_mode="HTML",
            reply_markup=_teaser_keyboard(),
        )
        return

    try:
        vm = await build_owner_snapshot()
        text = format_owner_report(vm)
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_nav_keyboard(),
        )
    except Exception:
        logger.exception("Ошибка обновления Insights")
        await callback.answer("Не удалось обновить", show_alert=True)


@router.callback_query(F.data == "insights_to_menu")
async def insights_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu,
        )
