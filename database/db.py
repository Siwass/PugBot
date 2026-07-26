import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///pugbot.db"

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _ensure_column(conn, table: str, column: str, ddl: str) -> None:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    if column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def _purge_legacy_cybertrip_data(conn) -> None:
    """
    Удаляет остатки CyberTrip из БД (каналы и связанные записи).
    Нужно после ребрендинга, если файл БД был переименован, а не создан заново.
    """
    try:
        result = await conn.execute(
            text(
                "SELECT id, title, username FROM channels "
                "WHERE lower(coalesce(title, '')) LIKE '%cybertrip%' "
                "   OR lower(coalesce(title, '')) LIKE '%cyber trip%' "
                "   OR lower(coalesce(username, '')) LIKE '%cybertrip%'"
            )
        )
        legacy = result.fetchall()
        if not legacy:
            return

        legacy_ids = [row[0] for row in legacy]
        logger.warning(
            "Обнаружены legacy-каналы CyberTrip (%s шт.) — удаляем: %s",
            len(legacy_ids),
            [(r[0], r[1], r[2]) for r in legacy],
        )

        # Сброс default_channel_id, если указывал на legacy
        placeholders = ",".join(str(i) for i in legacy_ids)
        await conn.execute(
            text(
                f"UPDATE user_settings SET default_channel_id = NULL "
                f"WHERE default_channel_id IN ({placeholders})"
            )
        )
        # Отвязка постов
        await conn.execute(
            text(
                f"UPDATE posts SET channel_id = NULL "
                f"WHERE channel_id IN ({placeholders})"
            )
        )
        # Админы каналов
        await conn.execute(
            text(
                f"DELETE FROM channel_admins WHERE channel_id IN ({placeholders})"
            )
        )
        # Сами каналы
        await conn.execute(
            text(f"DELETE FROM channels WHERE id IN ({placeholders})")
        )
        logger.info("Legacy-каналы CyberTrip удалены из pugbot.db")
    except Exception:
        # Таблиц может ещё не быть при самом первом запуске
        logger.debug("purge legacy: таблицы ещё не готовы или ошибка", exc_info=True)


async def init_db():
    # Регистрируем модели в metadata
    import database.models  # noqa: F401


    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

        await _ensure_column(
            conn,
            "posts",
            "channel_id",
            "channel_id INTEGER REFERENCES channels(id)",
        )
        await _ensure_column(
            conn,
            "posts",
            "error_message",
            "error_message TEXT",
        )
        await _ensure_column(
            conn,
            "posts",
            "telegram_message_id",
            "telegram_message_id BIGINT",
        )
        await _ensure_column(
            conn,
            "posts",
            "telegram_chat_id",
            "telegram_chat_id BIGINT",
        )
        await _ensure_column(
            conn,
            "posts",
            "published_at",
            "published_at DATETIME",
        )
        await _ensure_column(
            conn,
            "posts",
            "deleted_at",
            "deleted_at DATETIME",
        )


        await _ensure_column(
            conn,
            "posts",
            "auto_delete_hours",
            "auto_delete_hours INTEGER",
        )
        await _ensure_column(
            conn,
            "posts",
            "auto_delete_at",
            "auto_delete_at DATETIME",
        )
        await _ensure_column(
            conn,
            "user_settings",
            "timezone",
            "timezone VARCHAR(64)",
        )
        await _ensure_column(
            conn,
            "user_settings",
            "default_auto_delete_hours",
            "default_auto_delete_hours INTEGER",
        )

        await _purge_legacy_cybertrip_data(conn)
