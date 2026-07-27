"""Проверка ролей и доступа к PugBot.

Публичный релиз: любой пользователь Telegram может пользоваться ботом.
Таблица bot_admins — только служебные администраторы проекта (не gate доступа).
OWNER_ID / is_owner — владелец: Insights, управление администраторами.
"""

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
    Публичный доступ: любой пользователь может пользоваться PugBot.

    Зарезервировано под будущий ban-list (сейчас всегда True).
    Не проверяет bot_admins — эта таблица больше не является gate доступа.
    """
    _ = user_id
    return True


async def is_project_owner(user_id: int) -> bool:
    """
    Владелец проекта: OWNER_ID из env или запись BotAdmin с is_owner=True.
    Только владелец видит полную аналитику и раздел «Администраторы».
    """
    if OWNER_ID is not None and user_id == OWNER_ID:
        return True
    async with AsyncSessionLocal() as session:
        admin = await BotAdminRepository(session).get(user_id)
        return bool(admin and admin.is_owner)


def is_owner_id(user_id: int | None) -> bool:
    """Синхронная проверка по OWNER_ID (для клавиатур без async)."""
    return (
        OWNER_ID is not None
        and user_id is not None
        and user_id == OWNER_ID
    )
