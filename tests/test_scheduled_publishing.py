import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.channel_repository import ChannelRepository
from database.db import Base
from database.post_repository import PostRepository
from services.channel_resolver import get_active_channel, get_publish_chat_id
from services.scheduled_publisher import publish_due_posts


class ScheduledPublishingTests(unittest.IsolatedAsyncioTestCase):
    CHANNEL_CHAT_ID = -100123

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await self.create_channel()

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def create_channel(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)
            await repo.create(
                telegram_chat_id=self.CHANNEL_CHAT_ID,
                title="Test Channel",
                username="test_channel",
            )

    async def create_scheduled_post(
        self,
        text: str,
        publish_at: datetime,
    ):
        async with self.session_factory() as session:
            repo = PostRepository(session)
            post = await repo.create(author_id=1)
            await repo.update_text(post.id, text)
            return await repo.schedule_post(post.id, publish_at)

    async def get_status(self, post_id: int) -> str:
        async with self.session_factory() as session:
            post = await PostRepository(session).get_by_id(post_id)
            return post.status

    async def test_publishes_only_due_posts(self):
        now = datetime(2026, 7, 23, 18, 0)
        due_post = await self.create_scheduled_post("Пора в путь", now)
        future_post = await self.create_scheduled_post(
            "Ещё рано",
            now + timedelta(minutes=1),
        )
        bot = AsyncMock()

        published_count = await publish_due_posts(
            bot,
            now=now,
            session_factory=self.session_factory,
        )

        self.assertEqual(published_count, 1)
        self.assertEqual(await self.get_status(due_post.id), "published")
        self.assertEqual(await self.get_status(future_post.id), "scheduled")
        bot.send_message.assert_awaited_once_with(
            chat_id=self.CHANNEL_CHAT_ID,
            text="Пора в путь",
            reply_markup=None,
        )

    async def test_failed_publication_is_not_retried_automatically(self):
        now = datetime(2026, 7, 23, 18, 0)
        post = await self.create_scheduled_post("Пост с ошибкой", now)
        bot = AsyncMock()
        bot.send_message.side_effect = RuntimeError("Telegram недоступен")

        published_count = await publish_due_posts(
            bot,
            now=now,
            session_factory=self.session_factory,
        )

        self.assertEqual(published_count, 0)
        self.assertEqual(await self.get_status(post.id), "failed")

    async def test_claimed_post_cannot_be_claimed_twice(self):
        now = datetime(2026, 7, 23, 18, 0)
        post = await self.create_scheduled_post("Без дублей", now)

        async with self.session_factory() as session:
            claimed_posts = await PostRepository(session).claim_due_posts(now)

        async with self.session_factory() as session:
            repeated_claim = await PostRepository(session).claim_due_posts(now)

        self.assertEqual([item.id for item in claimed_posts], [post.id])
        self.assertEqual(repeated_claim, [])
        self.assertEqual(await self.get_status(post.id), "publishing")


class ChannelResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_get_active_channel_from_database(self):
        async with self.session_factory() as session:
            await ChannelRepository(session).create(
                telegram_chat_id=-100777,
                title="DB Channel",
                username="db_channel",
            )

        active = await get_active_channel(session_factory=self.session_factory)

        self.assertIsNotNone(active)
        self.assertEqual(active.telegram_chat_id, -100777)
        self.assertTrue(active.from_database)

    @patch("services.channel_resolver.CHANNEL_ID", "@fallback_channel")
    async def test_get_active_channel_falls_back_to_env(self):
        active = await get_active_channel(session_factory=self.session_factory)

        self.assertIsNotNone(active)
        self.assertEqual(active.telegram_chat_id, "@fallback_channel")
        self.assertFalse(active.from_database)

    @patch("services.channel_resolver.CHANNEL_ID", None)
    async def test_get_publish_chat_id_raises_without_channel(self):
        with self.assertRaises(ValueError):
            await get_publish_chat_id(session_factory=self.session_factory)


if __name__ == "__main__":
    unittest.main()
