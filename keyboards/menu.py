from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import OFFICIAL_CHANNEL_URL

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Новый пост"),
        ],
        [
            KeyboardButton(text="📂 Черновики"),
            KeyboardButton(text="📅 Очередь"),
        ],
        [
            KeyboardButton(text="📚 История"),
            KeyboardButton(text="🗑 Посты"),
        ],
        [
            KeyboardButton(text="📋 Шаблоны"),
        ],
        [
            KeyboardButton(text="⚙️ Настройки"),
            KeyboardButton(text="📊 Аналитика"),
        ],
        [
            KeyboardButton(text="⭐ Отзывы"),
            KeyboardButton(text="🛠 Поддержка"),
        ],
        [
            KeyboardButton(text="ℹ️ О боте"),
        ],
    ],
    resize_keyboard=True,
)


def official_channel_keyboard() -> InlineKeyboardMarkup:
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


def about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Официальный канал",
                    url=OFFICIAL_CHANNEL_URL,
                )
            ]
        ]
    )
