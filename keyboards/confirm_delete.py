from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

confirm_delete_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data="confirm_delete"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_delete"
            )
        ]
    ]
)