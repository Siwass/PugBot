from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.channel_roles import ChannelRole
from database.models import Channel, ChannelAdmin


class ChannelRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        telegram_chat_id: int,
        title: str,
        username: str | None,
    ) -> Channel | None:
        if await self.exists(telegram_chat_id):
            return None

        channel = Channel(
            telegram_chat_id=telegram_chat_id,
            title=title,
            username=username,
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def get_by_chat_id(
        self,
        telegram_chat_id: int,
    ) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(
                Channel.telegram_chat_id == telegram_chat_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> Channel | None:
        result = await self.session.execute(
            select(Channel).order_by(Channel.created_at.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def exists(self, telegram_chat_id: int) -> bool:
        return await self.get_by_chat_id(telegram_chat_id) is not None

    async def update_info(
        self,
        *,
        telegram_chat_id: int,
        title: str,
        username: str | None,
    ) -> Channel | None:
        channel = await self.get_by_chat_id(telegram_chat_id)

        if channel is None:
            return None

        channel.title = title
        channel.username = username

        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def get_channels_for_user(
        self,
        user_id: int,
    ) -> list[Channel]:
        result = await self.session.execute(
            select(Channel)
            .join(ChannelAdmin, ChannelAdmin.channel_id == Channel.id)
            .where(ChannelAdmin.user_id == user_id)
            .order_by(Channel.created_at.asc())
        )
        return list(result.scalars().unique().all())

    async def get_admin(
        self,
        channel_id: int,
        user_id: int,
    ) -> ChannelAdmin | None:
        result = await self.session.execute(
            select(ChannelAdmin).where(
                ChannelAdmin.channel_id == channel_id,
                ChannelAdmin.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_admin_if_absent(
        self,
        *,
        channel_id: int,
        user_id: int,
        role: str = ChannelRole.OWNER,
    ) -> ChannelAdmin | None:
        existing = await self.get_admin(channel_id, user_id)
        if existing is not None:
            return None

        admin = ChannelAdmin(
            channel_id=channel_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def get_all(self) -> list[Channel]:
        """Получить все каналы"""
        result = await self.session.execute(
            select(Channel).order_by(Channel.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        channel_id: int,
    ) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(
                Channel.id == channel_id
            )
        )
        return result.scalar_one_or_none()