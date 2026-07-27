import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner, ChatMemberUpdated, User

from database.channel_roles import ChannelRole
from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal

router = Router(name="channels")
logger = logging.getLogger(__name__)

# Служебные аккаунты Telegram (нельзя писать, не люди)
SERVICE_USER_IDS = {
    136817688,   # Channel_Bot / действия от имени канала
    1087968824,  # GroupAnonymousBot
    777000,      # Telegram
}

INSUFFICIENT_RIGHTS_TEXT = (
    "❌ <b>Недостаточно прав</b> для публикации в канале «{title}».\n\n"
    "Добавьте бота администратором с правом публикации сообщений."
)

CHANNEL_CONNECTED_TEXT = (
    "✅ <b>Канал успешно подключён</b>\n\n"
    "Название:\n"
    "{title}\n\n"
    "ID:\n"
    "<code>{chat_id}</code>\n\n"
    "Теперь можно публиковать посты.\n"
    "Откройте ⚙️ Настройки → 📺 Каналы."
)

CHANNEL_LEFT_TEXT = "ℹ️ Бот покинул канал «{title}»."


def _is_service_user(user: User | None) -> bool:
    if user is None:
        return True
    if user.is_bot:
        return True
    if user.id in SERVICE_USER_IDS:
        return True
    return False


def _bot_can_post(member: ChatMemberAdministrator | ChatMemberOwner) -> bool:
    if isinstance(member, ChatMemberOwner):
        return True
    return member.can_post_messages is not False


async def _resolve_owner_user_ids(
    bot: Bot,
    chat_id: int,
    event_user: User | None,
) -> list[int]:
    """
    Кого привязать как владельца канала в БД.

    event.from_user при добавлении бота в канал часто = Channel_Bot (136817688).
    """
    if event_user is not None and not _is_service_user(event_user):
        return [event_user.id]

    owner_ids: list[int] = []
    try:
        members = await bot.get_chat_administrators(chat_id)
    except Exception:
        logger.exception(
            "Не удалось получить администраторов канала %s",
            chat_id,
        )
        return owner_ids

    for member in members:
        user = member.user
        if user is None or _is_service_user(user):
            continue
        if member.status == ChatMemberStatus.CREATOR:
            owner_ids.insert(0, user.id)
        elif member.status == ChatMemberStatus.ADMINISTRATOR:
            if isinstance(member, ChatMemberAdministrator):
                if member.can_post_messages or member.can_manage_chat:
                    owner_ids.append(user.id)
            else:
                owner_ids.append(user.id)

    seen: set[int] = set()
    unique: list[int] = []
    for uid in owner_ids:
        if uid not in seen:
            seen.add(uid)
            unique.append(uid)
    return unique


async def _handle_bot_channel_membership(
    event: ChatMemberUpdated,
    bot: Bot,
) -> None:
    chat = event.chat
    new_member = event.new_chat_member
    event_user = event.from_user
    title = chat.title or "Без названия"
    chat_id = chat.id

    logger.debug(
        "my_chat_member: chat_id=%s title=%r type=%s status=%s from_user=%s",
        chat_id,
        title,
        chat.type,
        getattr(new_member, "status", None),
        event_user.id if event_user else None,
    )

    # Интересуют только каналы (не группы)
    chat_type = chat.type
    if hasattr(chat_type, "value"):
        chat_type = chat_type.value
    if str(chat_type) != "channel":
        logger.debug("my_chat_member: пропускаем chat type=%s", chat_type)
        return

    if new_member.status in ("left", "kicked"):
        for uid in await _resolve_owner_user_ids(bot, chat_id, event_user):
            await _notify_user(bot, uid, CHANNEL_LEFT_TEXT.format(title=title))
        return

    if not isinstance(new_member, (ChatMemberAdministrator, ChatMemberOwner)):
        logger.warning(
            "Бот в канале %s не администратор (status=%s) — канал не сохраняем",
            chat_id,
            getattr(new_member, "status", None),
        )
        for uid in await _resolve_owner_user_ids(bot, chat_id, event_user):
            await _notify_user(
                bot,
                uid,
                INSUFFICIENT_RIGHTS_TEXT.format(title=title),
            )
        return

    if not _bot_can_post(new_member):
        logger.warning(
            "У бота нет права can_post_messages в канале %s",
            chat_id,
        )
        for uid in await _resolve_owner_user_ids(bot, chat_id, event_user):
            await _notify_user(
                bot,
                uid,
                INSUFFICIENT_RIGHTS_TEXT.format(title=title),
            )
        return

    owner_ids: list[int] = []
    try:
        async with AsyncSessionLocal() as session:
            repo = ChannelRepository(session)

            if await repo.exists(chat_id):
                channel = await repo.update_info(
                    telegram_chat_id=chat_id,
                    title=title,
                    username=chat.username,
                )
                logger.debug(
                    "Канал %s обновлён в БД (id=%s)",
                    chat_id,
                    channel.id if channel else None,
                )
            else:
                channel = await repo.create(
                    telegram_chat_id=chat_id,
                    title=title,
                    username=chat.username,
                )
                logger.debug(
                    "Канал %s создан в БД (id=%s)",
                    chat_id,
                    channel.id if channel else None,
                )

            if channel is None:
                channel = await repo.get_by_chat_id(chat_id)

            if channel is None:
                logger.error("Не удалось сохранить/найти канал %s в БД", chat_id)
                return

            owner_ids = await _resolve_owner_user_ids(bot, chat_id, event_user)
            if not owner_ids:
                logger.warning(
                    "Канал %s сохранён, но не найден человеческий владелец "
                    "(from_user=%s).",
                    chat_id,
                    event_user.id if event_user else None,
                )
            else:
                for uid in owner_ids:
                    await repo.add_admin_if_absent(
                        channel_id=channel.id,
                        user_id=uid,
                        role=ChannelRole.OWNER,
                    )
                    logger.debug(
                        "Пользователь %s привязан к каналу %s (db id=%s)",
                        uid,
                        chat_id,
                        channel.id,
                    )
    except Exception:
        logger.exception("Ошибка записи канала %s в БД", chat_id)
        return

    for uid in owner_ids:
        await _notify_user(
            bot,
            uid,
            CHANNEL_CONNECTED_TEXT.format(title=title, chat_id=chat_id),
        )


@router.my_chat_member()
async def on_bot_my_chat_member(event: ChatMemberUpdated, bot: Bot) -> None:
    """Любое изменение статуса бота в чате (канал / группа / супергруппа)."""
    await _handle_bot_channel_membership(event, bot)


async def _notify_user(bot: Bot, user_id: int, text: str) -> None:
    if user_id in SERVICE_USER_IDS:
        logger.debug("Пропуск уведомления служебному аккаунту %s", user_id)
        return
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
        )
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(
            "Не удалось отправить уведомление пользователю %s: %s",
            user_id,
            e,
        )
    except Exception:
        logger.exception("Ошибка уведомления пользователя %s", user_id)
