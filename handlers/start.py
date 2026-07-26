import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from config import APP_NAME, APP_VERSION, OFFICIAL_CHANNEL_URL
from keyboards.menu import main_menu

router = Router()

_WELCOME_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "assets" / "welcome.png",
    Path(__file__).resolve().parent.parent / "assets" / "welcome.jpg",
    Path(__file__).resolve().parent.parent / "assets" / "welcome.jpeg",
    Path(__file__).resolve().parent.parent / "assets" / "welcome.webp",
)

WELCOME_TEXT = (
    f"🐶 <b>Добро пожаловать в {APP_NAME} v{APP_VERSION}</b>\n\n"
    f"{APP_NAME} — инструмент для создания, планирования\n"
    "и публикации постов в Telegram.\n\n"
    "🚀 <b>Основные возможности:</b>\n\n"
    "✍️ Создание и публикация постов\n"
    "📅 Отложенная публикация\n"
    "📋 Очередь публикаций\n"
    "📂 Черновики\n"
    "📝 Шаблоны постов\n"
    "📚 История публикаций\n"
    "📺 Работа с несколькими каналами\n"
    "👥 Управление администраторами\n"
    "🌍 Часовые пояса\n"
    "⏳ Автоудаление публикаций\n"
    "📊 Аналитика проекта (PugBot Insights)\n\n"
    "📢 <b>Следите за обновлениями</b>\n"
    "Официальный канал — новости, советы и новые функции.\n\n"
    "❤️ Спасибо, что выбрали PugBot"
)


def _welcome_image() -> FSInputFile | None:
    for path in _WELCOME_CANDIDATES:
        if path.is_file():
            return FSInputFile(path)
    return None


def _welcome_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на официальный канал",
                    url=OFFICIAL_CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Начать работу",
                    callback_data="start_begin",
                )
            ],
        ]
    )


def _subscribe_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на официальный канал",
                    url=OFFICIAL_CHANNEL_URL,
                )
            ]
        ]
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    # Снимаем reply-клавиатуру. Сообщение НЕ удаляем сразу —
    # иначе клиент Telegram часто «не успевает» применить Remove.
    await message.answer(
        "👋 Добро пожаловать!",
        reply_markup=ReplyKeyboardRemove(),
    )

    photo = _welcome_image()
    markup = _welcome_inline_keyboard()

    if photo is not None:
        try:
            await message.answer_photo(
                photo=photo,
                caption=WELCOME_TEXT,
                parse_mode="HTML",
                reply_markup=markup,
            )
            return
        except Exception:
            # Если фото не ушло — fallback на текст, UX не ломаем
            pass

    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=markup,
    )


@router.callback_query(F.data == "start_begin")
async def start_begin(callback: CallbackQuery) -> None:
    await callback.answer()

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=_subscribe_only_keyboard()
            )
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        await callback.message.answer(
            "👇 <b>Главное меню</b>\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=main_menu,
        )
