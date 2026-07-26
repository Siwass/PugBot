import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from config import DEFAULT_TIMEZONE
from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from services.publishing import publish_post

logger = logging.getLogger(__name__)

try:
    from utils.admin_notify import notify_publish_error
    from utils.last_error import set_last_error
except Exception:  # pragma: no cover
    notify_publish_error = None
    set_last_error = None


def _default_tz() -> ZoneInfo:
    try:
        return ZoneInfo(DEFAULT_TIMEZONE or "Europe/Kyiv")
    except Exception:
        return ZoneInfo("Europe/Kyiv")


POLL_INTERVAL_SECONDS = 30


def get_local_now() -> datetime:
    """Глобальное «сейчас» для планировщика (дефолтный пояс)."""
    return datetime.now(_default_tz()).replace(tzinfo=None, microsecond=0)


async def publish_due_posts(
    bot: Bot,
    *,
    now: datetime | None = None,
    session_factory=AsyncSessionLocal,
) -> int:
    publish_time = now or get_local_now()

    async with session_factory() as session:
        repo = PostRepository(session)
        posts = await repo.claim_due_posts(publish_time)

    published_count = 0

    for post in posts:
        try:
            message_id, chat_id = await publish_post(
                bot, post, session_factory=session_factory
            )
        except Exception as exc:
            logger.exception("Не удалось опубликовать пост %s", post.id)
            if set_last_error:
                set_last_error(str(exc), context=f"scheduled_publish post_id={post.id}")
            if notify_publish_error:
                try:
                    await notify_publish_error(
                        bot, post_id=post.id, error=str(exc)
                    )
                except Exception:
                    logger.exception("Не удалось уведомить админ-группу")

            async with session_factory() as session:
                repo = PostRepository(session)
                await repo.mark_publish_failed(post.id, error_message=str(exc))
            continue

        published_at = get_local_now()
        auto_delete_at = None
        if post.auto_delete_hours:
            auto_delete_at = published_at + timedelta(hours=post.auto_delete_hours)

        async with session_factory() as session:
            repo = PostRepository(session)
            await repo.mark_published(
                post.id,
                telegram_message_id=message_id,
                telegram_chat_id=chat_id,
                published_at=published_at,
            )
            if auto_delete_at is not None:
                await repo.set_auto_delete(
                    post.id,
                    post.auto_delete_hours,
                    auto_delete_at=auto_delete_at,
                )

        published_count += 1

    return published_count


async def process_auto_deletes(
    bot: Bot,
    *,
    now: datetime | None = None,
    session_factory=AsyncSessionLocal,
) -> int:
    """Удаляет из канала посты с наступившим auto_delete_at."""
    check_time = now or get_local_now()
    deleted = 0

    async with session_factory() as session:
        repo = PostRepository(session)
        posts = await repo.claim_due_auto_deletes(check_time)

    for post in posts:
        if not post.telegram_message_id or not post.telegram_chat_id:
            continue
        try:
            await bot.delete_message(
                chat_id=post.telegram_chat_id,
                message_id=post.telegram_message_id,
            )
        except Exception as exc:
            logger.warning(
                "Автоудаление поста %s не удалось: %s",
                post.id,
                exc,
            )
            # Снимаем флаг, чтобы не крутить бесконечно
            async with session_factory() as session:
                repo = PostRepository(session)
                await repo.set_auto_delete(post.id, None, auto_delete_at=None)
            continue

        async with session_factory() as session:
            repo = PostRepository(session)
            await repo.mark_deleted(post.id)
            await repo.set_auto_delete(post.id, None, auto_delete_at=None)
        deleted += 1
        logger.info("Пост %s автоудалён из канала", post.id)

    return deleted


async def recover_interrupted_publications(
    *,
    session_factory=AsyncSessionLocal,
) -> int:
    async with session_factory() as session:
        repo = PostRepository(session)
        return await repo.recover_interrupted_publications()


async def run_scheduled_publisher(
    bot: Bot,
    *,
    poll_interval: int = POLL_INTERVAL_SECONDS,
) -> None:
    try:
        recovered_count = await recover_interrupted_publications()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Не удалось восстановить прерванные публикации")
    else:
        if recovered_count:
            logger.warning(
                "Запланированные посты возвращены в очередь: %s",
                recovered_count,
            )

    while True:
        try:
            await publish_due_posts(bot)
            await process_auto_deletes(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка фоновой публикации")

        await asyncio.sleep(poll_interval)
