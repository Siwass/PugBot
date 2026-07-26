from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

confirm_publish_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Да, опубликовать",
                callback_data="confirm_publish",
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Вернуться к редактированию",
                callback_data="edit",
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_publish",
            )
        ],
    ]
)