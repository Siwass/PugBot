"""Хранение последней ошибки процесса для диагностики."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_KYIV = ZoneInfo("Europe/Kyiv")

_last: dict[str, Any] | None = None


def set_last_error(message: str, *, context: str | None = None) -> None:
    global _last
    _last = {
        "message": message,
        "context": context,
        "at": datetime.now(_KYIV).strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def get_last_error() -> dict[str, Any] | None:
    return _last
