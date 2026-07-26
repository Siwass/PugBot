"""Проверка доступа к PugBot по списку администраторов."""

from __future__ import annotations

from config import OWNER_ID
from database.bot_admin_repository import BotAdminRepository
from database.db import AsyncSessionLocal


async def ensure_owner_seeded() -> None:
    """При старте: если OWNER_ID задан — гарантируем запись владельца."""
    if not OWNER_ID:
        return
    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        await repo.ensure_owner(OWNER_ID)


async def user_has_access(user_id: int) -> bool:
    """
    True, если пользователь — администратор PugBot.
    Если список пуст и OWNER_ID не задан — доступ открыт (первый запуск).
    Если OWNER_ID задан — доступ только у admins (+ автосидинг owner).
    """
    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        count = await repo.count()

        if OWNER_ID and user_id == OWNER_ID:
            await repo.ensure_owner(OWNER_ID)
            return True

        if count == 0:
            # Пустая БД: пускаем всех, пока владелец не настроен
            if OWNER_ID:
                return user_id == OWNER_ID
            return True

        return await repo.is_admin(user_id)
