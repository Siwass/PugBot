"""Часовые пояса пользователя."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import DEFAULT_TIMEZONE

# Популярные пояса для UI
COMMON_TIMEZONES: tuple[tuple[str, str], ...] = (
    ("Europe/Kyiv", "🇺🇦 Киев (UTC+2/+3)"),
    ("Europe/Moscow", "🇷🇺 Москва (UTC+3)"),
    ("Europe/Minsk", "🇧🇾 Минск (UTC+3)"),
    ("Europe/Warsaw", "🇵🇱 Варшава (UTC+1/+2)"),
    ("Europe/Berlin", "🇩🇪 Берлин (UTC+1/+2)"),
    ("Europe/London", "🇬🇧 Лондон (UTC+0/+1)"),
    ("Asia/Almaty", "🇰🇿 Алматы (UTC+5)"),
    ("Asia/Tashkent", "🇺🇿 Ташкент (UTC+5)"),
    ("Asia/Yerevan", "🇦🇲 Ереван (UTC+4)"),
    ("Asia/Tbilisi", "🇬🇪 Тбилиси (UTC+4)"),
    ("America/New_York", "🇺🇸 Нью-Йорк (UTC-5/-4)"),
    ("UTC", "🌍 UTC"),
)


def resolve_timezone(name: str | None) -> ZoneInfo:
    key = (name or DEFAULT_TIMEZONE or "Europe/Kyiv").strip()
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Kyiv")


def get_user_now(timezone_name: str | None = None) -> datetime:
    """Текущее локальное время пользователя без tzinfo (для БД)."""
    tz = resolve_timezone(timezone_name)
    return datetime.now(tz).replace(tzinfo=None, microsecond=0)


def format_tz_label(timezone_name: str | None) -> str:
    key = timezone_name or DEFAULT_TIMEZONE
    for code, label in COMMON_TIMEZONES:
        if code == key:
            return label
    return key or DEFAULT_TIMEZONE
