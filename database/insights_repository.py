"""Агрегированная статистика для PugBot Insights.

Репозиторий только читает данные; без побочных эффектов.
Структура запросов рассчитана на расширение (графики, периоды, экспорт).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BotAdmin, Channel, Post, Template, UserSettings


@dataclass(frozen=True, slots=True)
class PostStatusCounts:
    draft: int = 0
    scheduled: int = 0
    publishing: int = 0
    published: int = 0
    failed: int = 0
    deleted: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class PeriodPublished:
    today: int = 0
    yesterday: int = 0
    last_7_days: int = 0
    last_30_days: int = 0


@dataclass(frozen=True, slots=True)
class InsightsSnapshot:
    """Снимок метрик. Добавление полей обратно-совместимо для UI."""

    admins_count: int
    channels_count: int
    templates_count: int
    users_with_settings: int
    posts: PostStatusCounts
    published_period: PeriodPublished
    pending_auto_delete: int
    collected_at: datetime


class InsightsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _count(self, model) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(model)
        )
        return int(result.scalar_one() or 0)

    async def _post_status_counts(self) -> PostStatusCounts:
        result = await self.session.execute(
            select(Post.status, func.count())
            .group_by(Post.status)
        )
        raw = {row[0]: int(row[1]) for row in result.all()}
        draft = raw.get("draft", 0)
        scheduled = raw.get("scheduled", 0)
        publishing = raw.get("publishing", 0)
        published = raw.get("published", 0)
        failed = raw.get("failed", 0)
        deleted = raw.get("deleted", 0)
        total = sum(raw.values())
        return PostStatusCounts(
            draft=draft,
            scheduled=scheduled,
            publishing=publishing,
            published=published,
            failed=failed,
            deleted=deleted,
            total=total,
        )

    async def _published_in_range(
        self,
        since: datetime | None,
        until: datetime | None,
    ) -> int:
        conditions = [Post.status == "published"]
        if since is not None:
            conditions.append(Post.published_at >= since)
        if until is not None:
            conditions.append(Post.published_at < until)
        result = await self.session.execute(
            select(func.count()).select_from(Post).where(*conditions)
        )
        return int(result.scalar_one() or 0)

    async def _period_published(self, now: datetime) -> PeriodPublished:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=6)
        month_start = today_start - timedelta(days=29)

        return PeriodPublished(
            today=await self._published_in_range(today_start, None),
            yesterday=await self._published_in_range(
                yesterday_start, today_start
            ),
            last_7_days=await self._published_in_range(week_start, None),
            last_30_days=await self._published_in_range(month_start, None),
        )

    async def _pending_auto_delete(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Post)
            .where(
                Post.status == "published",
                Post.auto_delete_at.is_not(None),
            )
        )
        return int(result.scalar_one() or 0)

    async def collect_snapshot(self, *, now: datetime) -> InsightsSnapshot:
        posts = await self._post_status_counts()
        period = await self._period_published(now)
        return InsightsSnapshot(
            admins_count=await self._count(BotAdmin),
            channels_count=await self._count(Channel),
            templates_count=await self._count(Template),
            users_with_settings=await self._count(UserSettings),
            posts=posts,
            published_period=period,
            pending_auto_delete=await self._pending_auto_delete(),
            collected_at=now,
        )
