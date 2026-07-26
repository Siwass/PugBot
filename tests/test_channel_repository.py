import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.channel_repository import ChannelRepository
from database.channel_roles import ChannelRole
from database.db import Base


class ChannelRepositoryTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_does_not_create_duplicate(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)

            channel = await repo.create(
                telegram_chat_id=-100500,
                title="CyberTrip",
                username="cybertrip",
            )
            duplicate = await repo.create(
                telegram_chat_id=-100500,
                title="CyberTrip Updated",
                username="cybertrip",
            )
            exists = await repo.exists(-100500)

        self.assertIsNotNone(channel)
        self.assertIsNone(duplicate)
        self.assertTrue(exists)

    async def test_update_info_updates_existing_channel(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)

            channel = await repo.create(
                telegram_chat_id=-100500,
                title="CyberTrip",
                username="cybertrip",
            )
            updated = await repo.update_info(
                telegram_chat_id=-100500,
                title="CyberTrip Updated",
                username="cybertrip",
            )

        self.assertEqual(updated.id, channel.id)
        self.assertEqual(updated.title, "CyberTrip Updated")

    async def test_add_admin_if_absent(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)
            channel = await repo.create(
                telegram_chat_id=-100501,
                title="Channel",
                username=None,
            )

            admin = await repo.add_admin_if_absent(
                channel_id=channel.id,
                user_id=42,
                role=ChannelRole.OWNER,
            )
            duplicate = await repo.add_admin_if_absent(
                channel_id=channel.id,
                user_id=42,
                role=ChannelRole.OWNER,
            )

        self.assertIsNotNone(admin)
        self.assertIsNone(duplicate)

    async def test_get_default_channel(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)
            first = await repo.create(
                telegram_chat_id=-100502,
                title="First",
                username=None,
            )
            await repo.create(
                telegram_chat_id=-100503,
                title="Second",
                username=None,
            )

            active = await repo.get_default()

        self.assertEqual(active.id, first.id)

    async def test_get_by_chat_id(self):
        async with self.session_factory() as session:
            repo = ChannelRepository(session)
            created = await repo.create(
                telegram_chat_id=-100504,
                title="Lookup",
                username="lookup",
            )

            found = await repo.get_by_chat_id(-100504)

        self.assertEqual(found.id, created.id)


if __name__ == "__main__":
    unittest.main()
