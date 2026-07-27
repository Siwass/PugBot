"""Операции с администраторами Telegram-канала через Bot API.

Используется разделом «👥 Администраторы» в настройках.
Не путать с таблицей bot_admins (служебные админы проекта).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

logger = logging.getLogger(__name__)

# Служебные аккаунты Telegram
SERVICE_USER_IDS = {
    136817688,
    1087968824,
    777000,
}


@dataclass(frozen=True, slots=True)
class ChannelAdminInfo:
    user_id: int
    full_name: str
    username: str | None
    is_creator: bool
    is_bot: bool


@dataclass(frozen=True, slots=True)
class BotPromoteStatus:
    is_admin: bool
    can_promote: bool
    detail: str | None = None


async def get_bot_promote_status(bot: Bot, chat_id: int) -> BotPromoteStatus:
    """Проверить, может ли бот назначать администраторов в канале."""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
    except TelegramForbiddenError:
        return BotPromoteStatus(
            is_admin=False,
            can_promote=False,
            detail="forbidden",
        )
    except TelegramBadRequest as e:
        logger.warning("get_chat_member bot in %s: %s", chat_id, e)
        return BotPromoteStatus(
            is_admin=False,
            can_promote=False,
            detail="bad_request",
        )
    except Exception:
        logger.exception("get_chat_member bot in %s", chat_id)
        return BotPromoteStatus(
            is_admin=False,
            can_promote=False,
            detail="error",
        )

    status = member.status
    if hasattr(status, "value"):
        status = status.value

    if status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, "left", "kicked"):
        return BotPromoteStatus(is_admin=False, can_promote=False, detail="left")

    if isinstance(member, ChatMemberOwner):
        return BotPromoteStatus(is_admin=True, can_promote=True)

    if isinstance(member, ChatMemberAdministrator):
        can = bool(member.can_promote_members)
        return BotPromoteStatus(is_admin=True, can_promote=can)

    return BotPromoteStatus(is_admin=False, can_promote=False, detail="not_admin")


async def list_human_admins(bot: Bot, chat_id: int) -> list[ChannelAdminInfo]:
    """Список человеческих администраторов канала (без служебных ботов)."""
    try:
        members = await bot.get_chat_administrators(chat_id)
    except Exception:
        logger.exception("get_chat_administrators %s", chat_id)
        raise

    result: list[ChannelAdminInfo] = []
    for member in members:
        user = member.user
        if user is None:
            continue
        if user.id in SERVICE_USER_IDS:
            continue
        is_creator = member.status == ChatMemberStatus.CREATOR or (
            hasattr(member.status, "value") and member.status.value == "creator"
        )
        result.append(
            ChannelAdminInfo(
                user_id=user.id,
                full_name=user.full_name or str(user.id),
                username=user.username,
                is_creator=bool(is_creator),
                is_bot=bool(user.is_bot),
            )
        )
    # Создатель первым, затем по имени
    result.sort(key=lambda a: (not a.is_creator, a.full_name.lower()))
    return result


async def promote_channel_admin(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> None:
    """
    Назначить пользователя администратором канала с правами публикации.

    Raises:
        TelegramForbiddenError, TelegramBadRequest, Exception
    """
    logger.info(
        "promote_channel_admin chat_id=%s user_id=%s",
        chat_id,
        user_id,
    )
    await bot.promote_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        can_post_messages=True,
        can_edit_messages=True,
        can_delete_messages=True,
        can_manage_chat=False,
        can_change_info=False,
        can_invite_users=True,
        can_restrict_members=False,
        can_promote_members=False,
        can_manage_video_chats=False,
        is_anonymous=False,
    )


async def demote_channel_admin(
    bot: Bot,
    chat_id: int,
    user_id: int,
) -> None:
    """Снять права администратора (все флаги False)."""
    logger.info(
        "demote_channel_admin chat_id=%s user_id=%s",
        chat_id,
        user_id,
    )
    await bot.promote_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        is_anonymous=False,
        can_manage_chat=False,
        can_delete_messages=False,
        can_manage_video_chats=False,
        can_restrict_members=False,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=False,
        can_post_messages=False,
        can_edit_messages=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )
