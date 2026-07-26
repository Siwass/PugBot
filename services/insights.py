"""PugBot Insights — слой аналитики.

Точка расширения: новые метрики, отчёты, экспорт добавляются сюда
и в InsightsRepository, без изменения handlers и UI-контрактов.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.db import AsyncSessionLocal
from database.insights_repository import InsightsRepository, InsightsSnapshot
from services.scheduled_publisher import get_local_now


@dataclass(frozen=True, slots=True)
class InsightsViewModel:
    """Данные, готовые к отображению. UI не знает о SQL."""

    snapshot: InsightsSnapshot
    is_owner_panel: bool = True


async def build_owner_snapshot() -> InsightsViewModel:
    now = get_local_now()
    async with AsyncSessionLocal() as session:
        repo = InsightsRepository(session)
        snap = await repo.collect_snapshot(now=now)
    return InsightsViewModel(snapshot=snap, is_owner_panel=True)


def format_owner_report(vm: InsightsViewModel) -> str:
    s = vm.snapshot
    p = s.posts
    per = s.published_period
    ts = s.collected_at.strftime("%d.%m.%Y %H:%M")

    return (
        "📊 <b>Аналитика</b>\n"
        f"<i>Снимок на {ts}</i>\n\n"
        "────────────\n"
        "<b>Команда</b>\n"
        f"👤 Администраторы: <b>{s.admins_count}</b>\n"
        f"📺 Каналы: <b>{s.channels_count}</b>\n"
        f"📋 Шаблоны: <b>{s.templates_count}</b>\n"
        f"⚙️ Настройки пользователей: <b>{s.users_with_settings}</b>\n\n"
        "────────────\n"
        "<b>Посты</b>\n"
        f"Всего: <b>{p.total}</b>\n"
        f"📂 Черновики: <b>{p.draft}</b>\n"
        f"📅 В очереди: <b>{p.scheduled}</b>\n"
        f"⏳ Публикуются: <b>{p.publishing}</b>\n"
        f"✅ Опубликовано: <b>{p.published}</b>\n"
        f"❌ Ошибки: <b>{p.failed}</b>\n"
        f"🗑 Удалено: <b>{p.deleted}</b>\n\n"
        "────────────\n"
        "<b>Публикации</b>\n"
        f"Сегодня: <b>{per.today}</b>\n"
        f"Вчера: <b>{per.yesterday}</b>\n"
        f"За 7 дней: <b>{per.last_7_days}</b>\n"
        f"За 30 дней: <b>{per.last_30_days}</b>\n\n"
        "────────────\n"
        f"⏳ Ожидают автоудаления: <b>{s.pending_auto_delete}</b>"
    )


TEASER_TEXT = (
    "📊 <b>Аналитика</b>\n\n"
    "Эта функция станет доступна всем пользователям "
    "в одном из следующих обновлений PugBot ❤️"
)
