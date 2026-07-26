from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

edit_buttons_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Добавить / заменить",
                callback_data="buttons_add",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить все",
                callback_data="buttons_delete",
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="edit",
            )
        ],
    ]
)