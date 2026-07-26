from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def queue_preview_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать текст",
                    callback_data=f"queue_edit_text_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✨ Форматировать",
                    callback_data=f"queue_format_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Медиа",
                    callback_data=f"queue_media_{post_id}",
                ),
                InlineKeyboardButton(
                    text="🔗 Кнопки",
                    callback_data=f"queue_buttons_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🕒 Изменить время",
                    callback_data=f"queue_time_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏳ Автоудаление",
                    callback_data="edit_autodel",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Опубликовать сейчас",
                    callback_data=f"queue_publish_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Дублировать",
                    callback_data=f"dup_post:{post_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"queue_delete_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="queue_back",
                )
            ],
        ]
    )
