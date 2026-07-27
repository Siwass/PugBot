from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserSettings


class UserSettingsRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> UserSettings | None:
        result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int) -> UserSettings:
        settings = await self.get(user_id)
        if settings:
            return settings

        settings = UserSettings(user_id=user_id)
        self.session.add(settings)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def set_default_channel(
        self,
        user_id: int,
        channel_id: int | None,
    ) -> UserSettings:
        settings = await self.get_or_create(user_id)
        settings.default_channel_id = channel_id
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def set_timezone(
        self,
        user_id: int,
        timezone: str | None,
    ) -> UserSettings:
        settings = await self.get_or_create(user_id)
        settings.timezone = timezone
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def set_default_auto_delete(
        self,
        user_id: int,
        hours: int | None,
    ) -> UserSettings:
        settings = await self.get_or_create(user_id)
        settings.default_auto_delete_hours = hours
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
