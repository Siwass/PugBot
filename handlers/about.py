from aiogram import F, Router
from aiogram.types import Message

from config import APP_NAME, APP_VERSION
from keyboards.menu import about_keyboard

router = Router()

ABOUT_TEXT = (
    f"🐶 <b>{APP_NAME} v{APP_VERSION}</b>\n\n"
    "Современный Telegram-бот для удобной\n"
    "публикации контента в каналы и группы.\n\n"
    "🚀 <b>Основные возможности:</b>\n\n"
    "✍️ Создание и публикация постов\n"
    "📅 Отложенная публикация\n"
    "📋 Очередь публикаций\n"
    "📂 Черновики\n"
    "📝 Шаблоны постов\n"
    "📚 История публикаций\n"
    "📺 Работа с несколькими каналами\n"
    "⭐ Отзывы и поддержка\n"
    "🌍 Часовые пояса\n"
    "⏳ Автоудаление публикаций\n"
    "📊 Аналитика проекта (PugBot Insights)\n\n"
    "❤️ Спасибо, что выбрали PugBot!\n\n"
    f"Версия: {APP_VERSION}"
)


@router.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer(
        ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=about_keyboard(),
    )
