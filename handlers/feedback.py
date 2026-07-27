"""Разделы «Отзывы» и «Поддержка». Сообщения уходят в админ-группу."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal
from database.user_settings_repository import UserSettingsRepository
from keyboards.menu import main_menu
from states.feedback import FeedbackStates
from utils.admin_notify import send_to_admin_group
from utils.debug_report import build_debug_report

router = Router()
logger = logging.getLogger(__name__)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

CANCEL_TEXT = "⬅️ Отмена"

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
    resize_keyboard=True,
)


def _user_line(message: Message) -> str:
    user = message.from_user
    if not user:
        return "—"
    name = user.full_name or "—"
    if user.username:
        return f"{name} (@{user.username})"
    return name


def _now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M")


def _support_after_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📎 Отправить диагностический лог",
                    callback_data="support_send_diag",
                )
            ]
        ]
    )


async def _channels_info(user_id: int) -> tuple[int, str | None]:
    try:
        async with AsyncSessionLocal() as session:
            channels = await ChannelRepository(session).get_channels_for_user(user_id)
            settings = await UserSettingsRepository(session).get(user_id)
            default_title = None
            if settings and settings.default_channel_id:
                for ch in channels:
                    if ch.id == settings.default_channel_id:
                        default_title = ch.title or "Канал"
                        break
            return len(channels), default_title
    except Exception:
        logger.exception("Не удалось получить каналы")
        return 0, None


@router.message(F.text == "⭐ Отзывы")
async def open_reviews(message: Message, state: FSMContext) -> None:
    await state.set_state(FeedbackStates.waiting_review)
    await message.answer(
        "⭐ <b>Отзыв</b>\n\nНапишите ваш отзыв одним сообщением.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )


@router.message(F.text == "🛠 Поддержка")
async def open_support(message: Message, state: FSMContext) -> None:
    await state.set_state(FeedbackStates.waiting_support)
    await message.answer(
        "🛠 <b>Поддержка</b>\n\nОпишите проблему одним сообщением.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )


@router.message(F.text == CANCEL_TEXT)
async def cancel_feedback(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu,
    )


@router.message(FeedbackStates.waiting_review)
async def receive_review(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ Нужен текстовый отзыв.")
        return
    if message.text == CANCEL_TEXT:
        await cancel_feedback(message, state)
        return

    report = (
        "⭐ <b>Новый отзыв</b>\n\n"
        f"👤 {_user_line(message)}\n\n"
        f"📝\n\n{message.text}\n\n"
        f"🕒\n{_now_str()}"
    )

    sent = await send_to_admin_group(message.bot, report)
    await state.clear()

    if sent:
        await message.answer(
            "✅ Спасибо! Ваш отзыв отправлен.",
            reply_markup=main_menu,
        )
    else:
        await message.answer(
            "✅ Спасибо! Отзыв принят, но доставить в админ-группу не удалось.",
            reply_markup=main_menu,
        )


@router.message(FeedbackStates.waiting_support)
async def receive_support(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ Опишите проблему текстом.")
        return
    if message.text == CANCEL_TEXT:
        await cancel_feedback(message, state)
        return

    report = (
        "🛠 <b>Новый запрос</b>\n\n"
        f"👤 {_user_line(message)}\n\n"
        f"💬\n\n{message.text}\n\n"
        f"🕒\n{_now_str()}"
    )

    sent = await send_to_admin_group(message.bot, report)

    await state.update_data(support_text=message.text, support_sent=sent)
    await state.set_state(FeedbackStates.support_done)

    if sent:
        await message.answer(
            "✅ Спасибо! Обращение отправлено.\n"
            "При необходимости можно отправить диагностический лог.",
            reply_markup=main_menu,
        )
        await message.answer(
            "Нужен диагностический лог?",
            reply_markup=_support_after_keyboard(),
        )
    else:
        await message.answer(
            "✅ Спасибо! Обращение принято, но доставить в админ-группу не удалось.",
            reply_markup=main_menu,
        )


@router.callback_query(F.data == "support_send_diag")
async def support_send_diag(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    user_id = callback.from_user.id
    count, default_ch = await _channels_info(user_id)
    data = await state.get_data()
    support_text = data.get("support_text")

    debug = await build_debug_report(
        callback.message,
        state,
        last_command="📎 Диагностический лог",
        channels_count=count,
        default_channel=default_ch,
        extra={"Исходное обращение": support_text or None},
    )

    # Отдельным сообщением — только диагностика
    report = f"📎 <b>Диагностический лог</b>\n\n{debug}"

    sent = await send_to_admin_group(callback.bot, report)

    if sent:
        await callback.message.edit_text("✅ Диагностический лог отправлен.")
    else:
        await callback.message.edit_text("❌ Не удалось отправить лог.")
    await state.clear()
