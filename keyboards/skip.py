from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="⏭ Пропустить")
        ]
    ],
    resize_keyboard=True
)