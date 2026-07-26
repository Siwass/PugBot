from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

schedule_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="⚡ Опубликовать сейчас")
        ],
        [
            KeyboardButton(text="📅 Запланировать")
        ]
    ],
    resize_keyboard=True
)