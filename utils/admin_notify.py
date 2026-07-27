"""Отправка служебных сообщений в админ-группу PugBot."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from config import ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


async def send_to_admin_group(
    bot: Bot,
    text: str,
    *,
    parse_mode: str | None = "HTML",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """
    Отправляет сообщение в 🛠 PugBot Admin.
    DEVELOPER_ID не используется.
    """
    if not ADMIN_GROUP_ID:
        logger.warning("ADMIN_GROUP_ID не задан — сообщение не отправлено")
        return False
    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(
            "Не удалось отправить в админ-группу %s: %s",
            ADMIN_GROUP_ID,
            e,
        )
        return False
    except Exception:
        logger.exception(
            "Ошибка отправки в админ-группу %s",
            ADMIN_GROUP_ID,
        )
        return False


async def notify_publish_error(
    bot: Bot,
    *,
    post_id: int | None,
    error: str,
    extra: dict[str, Any] | None = None,
) -> None:
    lines = [
        "❌ <b>Ошибка публикации</b>",
        "",
    ]
    if post_id is not None:
        lines.append(f"Post ID: <code>{post_id}</code>")
    lines.append(f"Ошибка: <code>{error[:1500]}</code>")
    if extra:
        for k, v in extra.items():
            if v is not None:
                lines.append(f"{k}: {v}")
    await send_to_admin_group(bot, "\n".join(lines))
