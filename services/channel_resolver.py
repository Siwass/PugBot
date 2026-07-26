from dataclasses import dataclass

from config import CHANNEL_ID
from database.db import AsyncSessionLocal
from database.channel_repository import ChannelRepository
from database.models import Channel


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


async def get_active_channel(
    *,
    session_factory=AsyncSessionLocal,
) -> ActiveChannel | None:
    """Возвращает 'основной' канал (пока первый из БД)"""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_default()  # или get_first()

    if channel is not None:
        return ActiveChannel.from_model(channel)

    if CHANNEL_ID:
        return ActiveChannel.from_env(CHANNEL_ID)

    return None


async def get_all_channels(
    *,
    session_factory=AsyncSessionLocal,
):
    """Новый метод — список всех подключённых каналов"""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_all()
    return channels


async def get_user_channels(
    user_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> list[Channel]:
    """Получить каналы пользователя для выбора публикации"""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        return await repo.get_channels_for_user(user_id)


async def get_channel_chat_id(
    channel_id: int,
    *,
    session_factory=AsyncSessionLocal,
) -> int | str | None:
    """Получить telegram_chat_id по ID канала из БД"""
    async with session_factory() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_by_id(channel_id)
        if channel:
            return channel.telegram_chat_id
    return None


async def get_publish_chat_id(
    *,
    session_factory=AsyncSessionLocal,
) -> int | str:
    active_channel = await get_active_channel(session_factory=session_factory)

    if active_channel is None:
        raise ValueError("Канал не настроен")

    return active_channel.telegram_chat_id