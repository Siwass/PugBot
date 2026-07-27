"""Единый UX для ошибок и устаревших меню."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def error_keyboard(
    *,
    retry_callback: str | None = None,
    back_callback: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if retry_callback:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔄 Повторить",
                    callback_data=retry_callback,
                )
            ]
        )
    if back_callback:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=back_callback,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="ux_to_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stale_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 Черновики",
                    callback_data="ux_open_drafts",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="ux_to_menu",
                )
            ],
        ]
    )


STALE_MENU_TEXT = (
    "ℹ️ <b>Это меню больше не актуально.</b>\n\n"
    "Откройте актуальный черновик\n"
    "или вернитесь в главное меню."
)


def format_error_text(detail: str | None = None) -> str:
    body = "❌ <b>Что-то пошло не так.</b>\n\n"
    if detail:
        body += f"{detail}\n\n"
    body += "────────────"
    return body


def format_publish_error(exc: BaseException) -> str:
    msg = str(exc) or type(exc).__name__
    lower = msg.lower()
    if "канал не настроен" in lower or "channel" in lower and "not" in lower:
        detail = (
            "Не выбран канал для публикации.\n"
            "Откройте ⚙️ Настройки → 📺 Каналы\n"
            "или задайте канал в настройках поста."
        )
    elif "forbidden" in lower or "can't" in lower or "нет прав" in lower:
        detail = (
            "Бот не может писать в канал.\n"
            "Проверьте права администратора бота\n"
            "(публикация сообщений)."
        )
    elif "chat not found" in lower:
        detail = "Канал не найден. Подключите канал заново."
    else:
        detail = "Не удалось опубликовать пост.\nПопробуйте ещё раз позже."
    return format_error_text(detail)
