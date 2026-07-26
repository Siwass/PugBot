from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def draft_preview_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Карточка черновика — тот же UX, что у очереди."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать текст",
                    callback_data=f"draft_edit_text_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✨ Форматировать",
                    callback_data=f"draft_format_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Медиа",
                    callback_data=f"draft_media_{post_id}",
                ),
                InlineKeyboardButton(
                    text="🔗 Кнопки",
                    callback_data=f"draft_buttons_{post_id}",
                ),
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
                    callback_data=f"draft_publish_{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Дублировать",
                    callback_data=f"dup_post:{post_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"draft_delete_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="drafts_back",
                )
            ],
        ]
    )
