"""Безопасный доступ к каналам пользователя.

Правило: любой channel_id / telegram_chat_id проверяется на принадлежность
текущему user_id (таблица channel_admins) и при необходимости — через
Telegram Bot API (пользователь всё ещё админ канала, бот в канале).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal
from database.models import Channel

logger = logging.getLogger(__name__)

CHANNEL_ACCESS_DENIED_TEXT = (
    "🚫 <b>У вас нет прав для управления данным каналом.</b>\n\n"
    "Убедитесь, что:\n"
    "• канал принадлежит вам;\n"
    "• вы являетесь его администратором;\n"
    "• PugBot добавлен в канал и имеет необходимые разрешения."
)

CHANNEL_NOT_LINKED_TEXT = (
    "📺 <b>Канал не подключён</b>\n\n"
    "Добавьте канал:\n"
    "⚙️ Настройки → 📺 Каналы → ➕ Добавить канал."
)


@dataclass(frozen=True, slots=True)
class ChannelAccessResult:
    ok: bool
    channel: Channel | None = None
    reason: str | None = None  # not_linked | not_owner | not_tg_admin | bot_missing | error


async def get_owned_channel(
    user_id: int,
    channel_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> Channel | None:
    """Канал из БД только если user_id есть в channel_admins."""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        admin = await repo.get_admin(channel_id, user_id)
        if admin is None:
            return None
        return await repo.get_by_id(channel_id)


async def get_owned_channel_by_chat_id(
    user_id: int,
    telegram_chat_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> Channel | None:
    async with session_factory() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_by_chat_id(telegram_chat_id)
        if channel is None:
            return None
        admin = await repo.get_admin(channel.id, user_id)
        if admin is None:
            return None
        return channel


async def user_owns_channel_id(
    user_id: int,
    channel_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> bool:
    return (
        await get_owned_channel(
            user_id, channel_id, session_factory=session_factory
        )
        is not None
    )


async def telegram_user_is_chat_admin(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> bool:
    """Живая проверка: пользователь — creator/administrator канала."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.info(
            "telegram_user_is_chat_admin fail chat=%s user=%s: %s",
            chat_id,
            user_id,
            e,
        )
        return False
    except Exception:
        logger.exception(
            "telegram_user_is_chat_admin error chat=%s user=%s",
            chat_id,
            user_id,
        )
        return False

    status = member.status
    if hasattr(status, "value"):
        status = status.value
    if status in (
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        "creator",
        "administrator",
    ):
        return True
    if isinstance(member, (ChatMemberOwner, ChatMemberAdministrator)):
        return True
    return False


async def telegram_bot_in_chat(bot: Bot, chat_id: int) -> bool:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
    except (TelegramForbiddenError, TelegramBadRequest):
        return False
    except Exception:
        logger.exception("telegram_bot_in_chat error chat=%s", chat_id)
        return False

    status = member.status
    if hasattr(status, "value"):
        status = status.value
    if status in ("left", "kicked", ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        return False
    return isinstance(member, (ChatMemberOwner, ChatMemberAdministrator)) or status in (
        "administrator",
        "creator",
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    )


async def verify_channel_access(
    bot: Bot | None,
    user_id: int,
    *,
    channel_id: int | None = None,
    telegram_chat_id: int | None = None,
    live_telegram: bool = True,
    session_factory=AsyncSessionLocal,
) -> ChannelAccessResult:
    """
    Полная проверка доступа к каналу.

    1) Запись в БД + channel_admins для user_id
    2) (если live_telegram и bot) пользователь — админ в Telegram
    3) (если live_telegram и bot) бот всё ещё в канале
    """
    channel: Channel | None = None
    if channel_id is not None:
        channel = await get_owned_channel(
            user_id, channel_id, session_factory=session_factory
        )
    elif telegram_chat_id is not None:
        channel = await get_owned_channel_by_chat_id(
            user_id, telegram_chat_id, session_factory=session_factory
        )

    if channel is None:
        return ChannelAccessResult(ok=False, reason="not_owner")

    if not live_telegram or bot is None:
        return ChannelAccessResult(ok=True, channel=channel)

    chat_id = channel.telegram_chat_id

    if not await telegram_bot_in_chat(bot, chat_id):
        return ChannelAccessResult(
            ok=False, channel=channel, reason="bot_missing"
        )

    if not await telegram_user_is_chat_admin(bot, chat_id, user_id):
        return ChannelAccessResult(
            ok=False, channel=channel, reason="not_tg_admin"
        )

    return ChannelAccessResult(ok=True, channel=channel)


async def resolve_chat_id_for_user(
    user_id: int,
    channel_id: int | None,
    *,
    session_factory=AsyncSessionLocal,
) -> int | None:
    """telegram_chat_id только для канала, принадлежащего user_id."""
    if channel_id is None:
        return None
    channel = await get_owned_channel(
        user_id, channel_id, session_factory=session_factory
    )
    if channel is None:
        return None
    return channel.telegram_chat_id


async def resolve_publish_chat_id(
    user_id: int,
    *,
    channel_id: int | None = None,
    session_factory=AsyncSessionLocal,
) -> int | None:
    """
    Цель публикации для пользователя.
    Если channel_id задан — только при ownership.
    Иначе — первый канал пользователя (не чужой «дефолт» из всей БД).
    """
    if channel_id is not None:
        return await resolve_chat_id_for_user(
            user_id, channel_id, session_factory=session_factory
        )

    async with session_factory() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_channels_for_user(user_id)
    if not channels:
        return None
    return channels[0].telegram_chat_id
