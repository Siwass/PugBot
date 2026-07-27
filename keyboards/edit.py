from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def edit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура редактирования поста"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Текст", callback_data="edit_text"),
                InlineKeyboardButton(text="🖼 Медиа", callback_data="edit_media"),
            ],
            [
                InlineKeyboardButton(text="🔗 Кнопки", callback_data="edit_buttons"),
                InlineKeyboardButton(text="📺 Канал", callback_data="edit_channel"),
            ],
            [
                InlineKeyboardButton(text="⏳ Автоудаление", callback_data="edit_autodel"),
            ],
            [
                InlineKeyboardButton(text="🕒 Расписание", callback_data="edit_schedule"),
            ],
            [
                InlineKeyboardButton(text="👀 Предпросмотр", callback_data="preview"),
            ],
        ]
    )
