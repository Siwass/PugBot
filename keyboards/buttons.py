from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

buttons_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔗 Добавить кнопку")
        ],
        [
            KeyboardButton(text="⬅ Назад")
        ]
    ],
    resize_keyboard=True
)
