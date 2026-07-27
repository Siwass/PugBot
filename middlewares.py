"""Access control middleware for PugBot (public release).

Любой пользователь Telegram может пользоваться ботом.
Middleware оставлен как точка расширения (будущий ban-list).
Служебные апдейты каналов не фильтруются.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from utils.access import user_has_access

logger = logging.getLogger(__name__)

# Команды/апдейты без проверки (каналы, membership)
_SKIP_UPDATE_TYPES = (
    "my_chat_member",
    "chat_member",
    "channel_post",
    "edited_channel_post",
)


class AccessControlMiddleware(BaseMiddleware):
    """Публичный доступ. Блокирует только при user_has_access == False (бан и т.п.)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        update: Update | None = event if isinstance(event, Update) else data.get("event_update")

        # Не режем служебные апдейты каналов
        if isinstance(update, Update):
            if update.my_chat_member or update.chat_member:
                return await handler(event, data)
            if update.channel_post or update.edited_channel_post:
                return await handler(event, data)

        user_id: int | None = None
        reply_target: Message | None = None

        if isinstance(event, Message):
            if event.from_user:
                user_id = event.from_user.id
            reply_target = event
        elif isinstance(event, CallbackQuery):
            if event.from_user:
                user_id = event.from_user.id
            if isinstance(event.message, Message):
                reply_target = event.message
        elif isinstance(update, Update):
            if update.message and update.message.from_user:
                user_id = update.message.from_user.id
                reply_target = update.message
            elif update.callback_query and update.callback_query.from_user:
                user_id = update.callback_query.from_user.id
                if isinstance(update.callback_query.message, Message):
                    reply_target = update.callback_query.message

        if user_id is None:
            return await handler(event, data)

        if await user_has_access(user_id):
            return await handler(event, data)

        logger.info("Доступ запрещён user_id=%s", user_id)
        text = (
            "⛔ <b>Нет доступа</b>\n\n"
            "Ваш доступ к PugBot ограничен.\n"
            "Обратитесь в поддержку."
        )
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            if reply_target is not None:
                await reply_target.answer(text, parse_mode="HTML")
        except Exception:
            pass
        return None
