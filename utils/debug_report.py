"""Компактная диагностика для админ-группы."""

from __future__ import annotations

from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import APP_NAME, APP_VERSION
from utils.last_error import get_last_error


def _format_state(state_name: str | None) -> str:
    if not state_name:
        return "—"
    if ":" in state_name:
        return state_name.rsplit(":", 1)[-1]
    return state_name


async def build_debug_report(
    message: Message,
    state: FSMContext | None = None,
    *,
    last_command: str | None = None,
    handler_name: str | None = None,
    exception: BaseException | None = None,
    extra: dict[str, Any] | None = None,
    channels_summary: str | None = None,
    channels_count: int | None = None,
    default_channel: str | None = None,
) -> str:
    lines: list[str] = []

    lines.append(f"<b>Версия:</b> {APP_NAME} {APP_VERSION}")

    user = message.from_user
    if user:
        uname = f"@{user.username}" if user.username else "—"
        lines.append(f"<b>Пользователь:</b> {user.full_name or '—'} ({uname})")
        lines.append(f"<b>ID:</b> <code>{user.id}</code>")

    if state is not None:
        try:
            current = await state.get_state()
            lines.append(f"<b>FSM:</b> {_format_state(current)}")
        except Exception:
            pass

    if last_command:
        lines.append(f"<b>Действие:</b> {last_command}")

    if channels_count is not None:
        lines.append(f"<b>Каналы:</b> {channels_count}")
    elif channels_summary is not None:
        lines.append(f"<b>Каналы:</b> {channels_summary}")

    if default_channel:
        lines.append(f"<b>Основной:</b> {default_channel}")

    if extra:
        for k, v in extra.items():
            if v is None:
                continue
            if k in (
                "User ID (from callback)",
                "Username (from callback)",
                "Chat ID",
                "Admin Group ID",
            ):
                continue
            lines.append(f"<b>{k}:</b> {v}")

    last_err = get_last_error()
    if last_err:
        msg = str(last_err.get("message", "—"))[:120]
        lines.append(f"<b>Ошибка:</b> {msg}")

    if exception is not None:
        lines.append(
            f"<b>Exception:</b> {type(exception).__name__}: {str(exception)[:200]}"
        )

    return "\n".join(lines)
