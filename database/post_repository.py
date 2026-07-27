import json
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Post


class PostRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, author_id: int) -> Post:
        post = Post(author_id=author_id)

        self.session.add(post)

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def get_by_id(
        self,
        post_id: int
    ) -> Post | None:

        result = await self.session.execute(
            select(Post).where(Post.id == post_id)
        )

        return result.scalar_one_or_none()

    async def get_drafts(
        self,
        author_id: int
    ) -> list[Post]:

        result = await self.session.execute(
            select(Post)
            .where(
                Post.author_id == author_id,
                Post.status == "draft"
            )
            .order_by(Post.created_at.desc())
        )

        return list(result.scalars().all())

    async def get_scheduled_posts(
        self,
        author_id: int
    ) -> list[Post]:

        result = await self.session.execute(
            select(Post)
            .where(
                Post.author_id == author_id,
                Post.status == "scheduled"
            )
            .order_by(Post.publish_at.asc())
        )

        return list(result.scalars().all())

    async def get_history(
        self,
        author_id: int,
        limit: int = 50,
    ) -> list[Post]:
        result = await self.session.execute(
            select(Post)
            .where(
                Post.author_id == author_id,
                Post.status.in_(("published", "failed", "deleted")),
            )
            .order_by(Post.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_published_posts(
        self,
        author_id: int,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Post]:
        """Опубликованные посты (ещё не удалённые из канала) за период."""
        conditions = [
            Post.author_id == author_id,
            Post.status == "published",
            Post.telegram_message_id.is_not(None),
        ]
        if since is not None:
            conditions.append(Post.published_at >= since)
        if until is not None:
            conditions.append(Post.published_at < until)

        # Сначала самые новые (published_at DESC, затем id DESC)
        result = await self.session.execute(
            select(Post)
            .where(*conditions)
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_text(
        self,
        post_id: int,
        text: str
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.text = text

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def update_media(
        self,
        post_id: int,
        media_type: str,
        file_ids: list[str]
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.media = json.dumps(
            {
                "type": media_type,
                "files": file_ids
            },
            ensure_ascii=False
        )

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def update_buttons(
        self,
        post_id: int,
        buttons: list[dict]
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.buttons = json.dumps(
            buttons,
            ensure_ascii=False
        )

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def update_channel(
        self,
        post_id: int,
        channel_id: int,
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.channel_id = channel_id

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def update_status(
        self,
        post_id: int,
        status: str
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.status = status

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def schedule_post(
        self,
        post_id: int,
        publish_at: datetime,
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.publish_at = publish_at
        post.status = "scheduled"
        post.error_message = None

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def claim_due_posts(
        self,
        now: datetime,
    ) -> list[Post]:
        result = await self.session.execute(
            select(Post.id)
            .where(
                Post.status == "scheduled",
                Post.publish_at.is_not(None),
                Post.publish_at <= now,
            )
            .order_by(Post.publish_at.asc())
        )

        post_ids = list(result.scalars().all())
        claimed_ids = []

        for post_id in post_ids:
            claim_result = await self.session.execute(
                update(Post)
                .where(
                    Post.id == post_id,
                    Post.status == "scheduled",
                )
                .values(status="publishing")
            )

            if claim_result.rowcount == 1:
                claimed_ids.append(post_id)

        if not claimed_ids:
            return []

        await self.session.commit()

        result = await self.session.execute(
            select(Post)
            .where(Post.id.in_(claimed_ids))
            .order_by(Post.publish_at.asc())
        )

        return list(result.scalars().all())

    async def recover_interrupted_publications(self) -> int:
        result = await self.session.execute(
            update(Post)
            .where(Post.status == "publishing")
            .values(status="scheduled")
        )

        await self.session.commit()

        return result.rowcount

    async def mark_publish_failed(
        self,
        post_id: int,
        error_message: str | None = None,
    ) -> Post | None:
        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.status = "failed"
        if error_message is not None:
            post.error_message = error_message[:500]

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def mark_published(
        self,
        post_id: int,
        *,
        telegram_message_id: int | None = None,
        telegram_chat_id: int | None = None,
        published_at: datetime | None = None,
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.status = "published"
        post.publish_at = None
        post.error_message = None
        post.deleted_at = None

        if telegram_message_id is not None:
            post.telegram_message_id = telegram_message_id
        if telegram_chat_id is not None:
            post.telegram_chat_id = telegram_chat_id
        if published_at is not None:
            post.published_at = published_at
        elif post.published_at is None:
            post.published_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def mark_deleted(
        self,
        post_id: int,
        *,
        deleted_at: datetime | None = None,
    ) -> Post | None:
        """Пометить пост как удалённый из канала (запись в БД сохраняется)."""
        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.status = "deleted"
        post.deleted_at = deleted_at or datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def update_publish_time(
        self,
        post_id: int,
        publish_at: datetime,
    ) -> Post | None:

        post = await self.get_by_id(post_id)

        if not post:
            return None

        post.publish_at = publish_at

        await self.session.commit()
        await self.session.refresh(post)

        return post

    async def delete_from_queue(
        self,
        post_id: int
    ) -> bool:

        post = await self.get_by_id(post_id)

        if not post:
            return False

        post.status = "draft"
        post.publish_at = None

        await self.session.commit()

        return True

    async def duplicate(
        self,
        post_id: int,
        author_id: int,
    ) -> Post | None:
        source = await self.get_by_id(post_id)

        if not source or source.author_id != author_id:
            return None

        copy = Post(
            author_id=author_id,
            channel_id=source.channel_id,
            text=source.text,
            media=source.media,
            buttons=source.buttons,
            status="draft",
            publish_at=None,
            error_message=None,
        )
        self.session.add(copy)
        await self.session.commit()
        await self.session.refresh(copy)
        return copy

    async def delete(
        self,
        post_id: int
    ) -> bool:

        post = await self.get_by_id(post_id)

        if not post:
            return False

        await self.session.delete(post)
        await self.session.commit()

        return True

    async def delete_all_drafts(
        self,
        author_id: int
    ) -> int:

        result = await self.session.execute(
            select(Post).where(
                Post.author_id == author_id,
                Post.status == "draft"
            )
        )

        posts = list(result.scalars().all())

        count = len(posts)

        for post in posts:
            await self.session.delete(post)

        await self.session.commit()

        return count

    async def set_auto_delete(
        self,
        post_id: int,
        hours: int | None,
        *,
        auto_delete_at: datetime | None = None,
    ) -> Post | None:
        post = await self.get_by_id(post_id)
        if not post:
            return None
        post.auto_delete_hours = hours
        post.auto_delete_at = auto_delete_at
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def claim_due_auto_deletes(
        self,
        now: datetime,
    ) -> list[Post]:
        """Посты, у которых наступило время автоудаления."""
        result = await self.session.execute(
            select(Post.id)
            .where(
                Post.status == "published",
                Post.auto_delete_at.is_not(None),
                Post.auto_delete_at <= now,
                Post.telegram_message_id.is_not(None),
            )
            .order_by(Post.auto_delete_at.asc())
        )
        post_ids = list(result.scalars().all())
        if not post_ids:
            return []

        result = await self.session.execute(
            select(Post)
            .where(Post.id.in_(post_ids))
            .order_by(Post.auto_delete_at.asc())
        )
        return list(result.scalars().all())
