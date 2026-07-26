import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, APP_NAME, APP_VERSION, OWNER_ID

from handlers.start import router as start_router
from handlers.channels import router as channels_router
from handlers.settings import router as settings_router
from handlers.about import router as about_router
from handlers.feedback import router as feedback_router
from handlers.insights import router as insights_router
from handlers.ux import router as ux_router
from handlers.post import router as post_router

from database.db import init_db
from middlewares import AccessControlMiddleware
from services.scheduled_publisher import run_scheduled_publisher
from utils.access import ensure_owner_seeded

import database.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("aiogram").setLevel(logging.INFO)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден")

    if not OWNER_ID:
        logger.warning(
            "OWNER_ID не задан. PugBot Insights будет недоступен."
        )

    await init_db()
    await ensure_owner_seeded()
    logger.info("База данных готова")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Доступ только администраторам PugBot
    dp.update.outer_middleware(AccessControlMiddleware())

    dp.include_router(channels_router)
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(about_router)
    dp.include_router(feedback_router)
    dp.include_router(insights_router)
    dp.include_router(ux_router)
    dp.include_router(post_router)

    used = dp.resolve_used_update_types()
    logger.info("%s v%s запущен", APP_NAME, APP_VERSION)
    if "my_chat_member" not in used:
        logger.warning("my_chat_member не в allowed_updates — добавляем")
        used = list(used) + ["my_chat_member"]

    scheduled_publisher_task = asyncio.create_task(
        run_scheduled_publisher(bot)
    )

    try:
        await dp.start_polling(bot, allowed_updates=used)
    finally:
        scheduled_publisher_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduled_publisher_task


if __name__ == "__main__":
    asyncio.run(main())
