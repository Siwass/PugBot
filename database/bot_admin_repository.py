from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BotAdmin


class BotAdminRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[BotAdmin]:
        result = await self.session.execute(
            select(BotAdmin).order_by(
                BotAdmin.is_owner.desc(),
                BotAdmin.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(BotAdmin)
        )
        return int(result.scalar_one() or 0)

    async def get(self, user_id: int) -> BotAdmin | None:
        result = await self.session.execute(
            select(BotAdmin).where(BotAdmin.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def is_admin(self, user_id: int) -> bool:
        return await self.get(user_id) is not None

    async def ensure_owner(
        self,
        user_id: int,
        *,
        display_name: str | None = None,
        username: str | None = None,
    ) -> BotAdmin:
        existing = await self.get(user_id)
        if existing:
            if not existing.is_owner:
                existing.is_owner = True
            if display_name:
                existing.display_name = display_name
            if username:
                existing.username = username
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        admin = BotAdmin(
            user_id=user_id,
            display_name=display_name,
            username=username,
            is_owner=True,
        )
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def add(
        self,
        user_id: int,
        *,
        display_name: str | None = None,
        username: str | None = None,
        is_owner: bool = False,
    ) -> BotAdmin | None:
        existing = await self.get(user_id)
        if existing is not None:
            return None

        admin = BotAdmin(
            user_id=user_id,
            display_name=display_name,
            username=username,
            is_owner=is_owner,
        )
        self.session.add(admin)
        await self.session.commit()
        await self.session.refresh(admin)
        return admin

    async def remove(self, user_id: int) -> bool:
        admin = await self.get(user_id)
        if admin is None:
            return False
        if admin.is_owner:
            return False
        await self.session.delete(admin)
        await self.session.commit()
        return True

    async def display_label(self, admin: BotAdmin) -> str:
        if admin.display_name:
            return admin.display_name
        if admin.username:
            return f"@{admin.username}"
        return str(admin.user_id)
