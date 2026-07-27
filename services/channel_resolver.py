"""Резолвер каналов.

Важно: глобальный «первый канал из БД» больше не используется для публикации.
Все операции с каналом должны идти через services.channel_access
с привязкой к user_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import CHANNEL_ID
from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal
from database.models import Channel
from services.channel_access import (
    get_owned_channel,
    resolve_chat_id_for_user,
    resolve_publish_chat_id,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ActiveChannel:
    telegram_chat_id: int | str
    title: str | None = None
    username: str | None = None
    from_database: bool = True

    @classmethod
    def from_model(cls, channel: Channel) -> "ActiveChannel":
        return cls(
            telegram_chat_id=channel.telegram_chat_id,
            title=channel.title,
            username=channel.username,
            from_database=True,
        )

    @classmethod
    def from_env(cls, chat_id: str) -> "ActiveChannel":
        normalized = chat_id.strip()

        if normalized.lstrip("-").isdigit():
            return cls(
                telegram_chat_id=int(normalized),
                title=None,
                username=None,
                from_database=False,
            )

        return cls(
            telegram_chat_id=normalized,
            title=None,
            username=normalized.lstrip("@") or None,
            from_database=False,
        )


async def get_user_channels(
    user_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> list[Channel]:
    """Каналы, к которым user_id привязан в channel_admins."""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        return await repo.get_channels_for_user(user_id)


async def get_channel_chat_id(
    channel_id: int,
    *,
    user_id: int | None = None,
    session_factory=AsyncSessionLocal,
) -> int | str | None:
    """
    telegram_chat_id по ID канала.

    Если передан user_id — только при ownership (безопасно).
    Без user_id — устаревший путь, только для внутренней совместимости;
    предпочтительно всегда передавать user_id.
    """
    if user_id is not None:
        return await resolve_chat_id_for_user(
            user_id, channel_id, session_factory=session_factory
        )

    logger.warning(
        "get_channel_chat_id(%s) без user_id — небезопасный вызов",
        channel_id,
    )
    async with session_factory() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_by_id(channel_id)
        if channel:
            return channel.telegram_chat_id
    return None


async def get_publish_chat_id(
    *,
    user_id: int | None = None,
    channel_id: int | None = None,
    session_factory=AsyncSessionLocal,
) -> int | str:
    """
    chat_id для публикации.

    Требует user_id. Без него — ValueError (раньше брался чужой «первый» канал).
    """
    if user_id is None:
        raise ValueError("Канал не настроен: не указан пользователь")

    chat_id = await resolve_publish_chat_id(
        user_id,
        channel_id=channel_id,
        session_factory=session_factory,
    )
    if chat_id is None:
        # Fallback env только если у пользователя нет каналов в БД
        # и явно задан CHANNEL_ID — для single-tenant legacy
        if CHANNEL_ID and channel_id is None:
            logger.warning(
                "publish fallback CHANNEL_ID for user_id=%s", user_id
            )
            active = ActiveChannel.from_env(CHANNEL_ID)
            return active.telegram_chat_id
        raise ValueError("Канал не настроен")

    return chat_id


async def get_active_channel_for_user(
    user_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> ActiveChannel | None:
    """Первый канал пользователя (не глобальный get_default)."""
    channels = await get_user_channels(user_id, session_factory=session_factory)
    if channels:
        return ActiveChannel.from_model(channels[0])
    if CHANNEL_ID:
        return ActiveChannel.from_env(CHANNEL_ID)
    return None


# Совместимость: старое имя больше не должно использоваться для чужих каналов
async def get_active_channel(
    *,
    session_factory=AsyncSessionLocal,
) -> ActiveChannel | None:
    logger.warning(
        "get_active_channel() без user_id устарел и небезопасен — "
        "используйте get_active_channel_for_user(user_id)"
    )
    if CHANNEL_ID:
        return ActiveChannel.from_env(CHANNEL_ID)
    return None


async def get_all_channels(
    *,
    session_factory=AsyncSessionLocal,
):
    """Все каналы в БД (только для системных задач OWNER/Insights)."""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        return await repo.get_all()
