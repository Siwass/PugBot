from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

preview_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Опубликовать",
                callback_data="publish"
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data="edit"
            ),
            InlineKeyboardButton(
                text="⏳ Автоудаление",
                callback_data="edit_autodel"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data="delete"
            )
        ]
    ]
)