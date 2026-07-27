"""Раздел «🗑 Посты» — просмотр и удаление опубликованных сообщений из канала."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.menu import main_menu
from keyboards.published_posts import (
    after_delete_keyboard,
    confirm_delete_keyboard,
    period_keyboard,
    post_actions_keyboard,
    posts_list_keyboard,
    _post_title,
)
from services.channel_access import get_owned_channel, resolve_chat_id_for_user
from services.scheduled_publisher import get_local_now

router = Router()
logger = logging.getLogger(__name__)

# Максимум постов в одном списке периода
PUBLISHED_LIST_LIMIT = 50

# Ошибки Telegram, при которых сообщение уже недоступно для удаления
_MESSAGE_GONE_MARKERS = (
    "message to delete not found",
    "message can't be deleted",
    "message not found",
    "message to delete not found",
    "bad request: message to delete not found",
    "message is not modified",
)


def _is_message_already_gone(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _MESSAGE_GONE_MARKERS)


def _period_bounds(period: str) -> tuple[datetime | None, datetime | None]:
    """Возвращает (since, until) для фильтра published_at."""
    now = get_local_now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today, today + timedelta(days=1)
    if period == "yesterday":
        return today - timedelta(days=1), today
    if period == "week":
        return today - timedelta(days=6), today + timedelta(days=1)
    return None, None


def _period_label(period: str) -> str:
    return {
        "today": "Сегодня",
        "yesterday": "Вчера",
        "week": "За неделю",
    }.get(period, period)


async def _load_posts(user_id: int, period: str):
    since, until = _period_bounds(period)
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        return await repo.get_published_posts(
            user_id,
            since=since,
            until=until,
            limit=PUBLISHED_LIST_LIMIT,
        )


async def _show_period_list(
    target: Message | CallbackQuery,
    user_id: int,
    period: str,
) -> None:
    posts = await _load_posts(user_id, period)
    label = _period_label(period)

    if isinstance(target, CallbackQuery):
        message = target.message
        if not isinstance(message, Message):
            return
        answer = message.answer
    else:
        answer = target.answer

    if not posts:
        await answer(
            f"🗑 <b>Посты · {label}</b>\n\n"
            "Нет опубликованных постов за этот период.\n"
            "(Учитываются только посты, опубликованные после обновления бота.)",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ К периодам",
                            callback_data="pub_periods",
                        )
                    ]
                ]
            ),
        )
        return

    count_line = f"Найдено: <b>{len(posts)}</b>"
    if len(posts) >= PUBLISHED_LIST_LIMIT:
        count_line = (
            f"Показаны последние <b>{PUBLISHED_LIST_LIMIT}</b> "
            "(самые новые)"
        )

    await answer(
        f"🗑 <b>Посты · {label}</b>\n\n"
        f"{count_line}\n"
        "Выберите пост:",
        parse_mode="HTML",
        reply_markup=posts_list_keyboard(posts, period),
    )


@router.message(F.text == "🗑 Посты")
async def published_entry(message: Message):
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "🗑 <b>Управление опубликованными постами</b>\n\n"
        "Выберите период:",
        parse_mode="HTML",
        reply_markup=period_keyboard(),
    )


@router.callback_query(F.data == "pub_periods")
async def published_periods(callback: CallbackQuery):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.answer(
        "🗑 <b>Управление опубликованными постами</b>\n\n"
        "Выберите период:",
        parse_mode="HTML",
        reply_markup=period_keyboard(),
    )


@router.callback_query(F.data == "pub_back_menu")
async def published_back_menu(callback: CallbackQuery):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu,
    )


@router.callback_query(F.data.startswith("pub_period:"))
async def published_period_list(callback: CallbackQuery):
    await callback.answer()
    if callback.data is None or callback.from_user is None:
        return
    if not isinstance(callback.message, Message):
        return

    period = callback.data.removeprefix("pub_period:")
    if period not in ("today", "yesterday", "week"):
        await callback.message.answer("❌ Некорректный период.")
        return

    await _show_period_list(callback, callback.from_user.id, period)


@router.callback_query(F.data.startswith("pub_open:"))
async def published_open(callback: CallbackQuery):
    await callback.answer()
    if callback.data is None or callback.from_user is None:
        return
    if not isinstance(callback.message, Message):
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    try:
        post_id = int(parts[1])
    except ValueError:
        return
    period = parts[2]

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != callback.from_user.id:
        await callback.message.answer("❌ Пост не найден.")
        return

    if post.status != "published":
        await callback.message.answer(
            "ℹ️ Этот пост уже не в списке опубликованных "
            f"(статус: {post.status})."
        )
        return

    # Дата публикации
    if post.published_at:
        date_str = post.published_at.strftime("%d.%m.%Y %H:%M")
    else:
        date_str = "—"

    # Канал
    channel_title = "—"
    if post.channel_id and callback.from_user is not None:
        channel = await get_owned_channel(
            callback.from_user.id, post.channel_id
        )
        if channel:
            channel_title = channel.title or str(channel.telegram_chat_id)

    header = (
        f"📄 <b>Пост №{post.id}</b>\n"
        f"🕒 {date_str} (Киев)\n"
        f"📺 {channel_title}\n"
        f"━━━━━━━━━━━━━━"
    )
    await callback.message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await callback.message.answer(header, parse_mode="HTML")

    # Предпросмотр содержимого
    keyboard = None
    if post.buttons:
        try:
            buttons = json.loads(post.buttons)
            if buttons:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=b["text"],
                                url=b["url"],
                            )
                        ]
                        for b in buttons
                    ]
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            keyboard = None

    try:
        if post.media:
            media = json.loads(post.media)
            if media.get("type") == "photo" and media.get("files"):
                await callback.message.answer_photo(
                    photo=media["files"][0],
                    caption=post.text or "",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await callback.message.answer(
                    post.text or "📷 Медиа",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            await callback.message.answer(
                post.text or "Пост без текста",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("Не удалось показать предпросмотр поста %s", post.id)
        await callback.message.answer(
            f"📄 {_post_title(post)}\n\n"
            "<i>Не удалось отобразить полный предпросмотр.</i>",
            parse_mode="HTML",
        )

    await callback.message.answer(
        "Выберите действие:",
        reply_markup=post_actions_keyboard(post.id, period),
    )


@router.callback_query(F.data.startswith("pub_delete:"))
async def published_delete_confirm(callback: CallbackQuery):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    try:
        post_id = int(parts[1])
    except ValueError:
        return
    period = parts[2]

    await callback.message.answer(
        "⚠️ <b>Вы действительно хотите удалить опубликованный пост?</b>\n\n"
        "Это действие нельзя отменить.\n"
        "Сообщение будет удалено из канала.",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard(post_id, period),
    )


@router.callback_query(F.data.startswith("pub_delete_yes:"))
async def published_delete_yes(callback: CallbackQuery):
    await callback.answer()
    if callback.data is None or callback.from_user is None:
        return
    if not isinstance(callback.message, Message):
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    try:
        post_id = int(parts[1])
    except ValueError:
        return
    period = parts[2]

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or post.author_id != callback.from_user.id:
            await callback.message.answer("❌ Пост не найден.")
            return

        if post.status != "published":
            await callback.message.answer(
                "ℹ️ Пост уже удалён или не опубликован."
            )
            return

        if not post.telegram_message_id:
            await callback.message.answer(
                "❌ Нет данных о сообщении в Telegram.\n"
                "Пост был опубликован до обновления бота — "
                "удалите его вручную в канале."
            )
            return

        chat_id = post.telegram_chat_id
        if chat_id is None and post.channel_id:
            chat_id = await resolve_chat_id_for_user(
                callback.from_user.id, post.channel_id
            )
        if chat_id is None:
            await callback.message.answer(
                "❌ Не удалось определить канал для удаления."
            )
            return

        try:
            await callback.bot.delete_message(
                chat_id=chat_id,
                message_id=post.telegram_message_id,
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.warning(
                "Не удалось удалить сообщение %s из чата %s: %s",
                post.telegram_message_id,
                chat_id,
                exc,
            )
            if _is_message_already_gone(exc):
                # Сообщение уже нет в канале — убираем из раздела «Посты»
                await repo.mark_deleted(post_id, deleted_at=get_local_now())
                await callback.message.answer(
                    "ℹ️ Сообщение уже было удалено из канала.\n"
                    "Запись обновлена и больше не отображается в «🗑 Посты».",
                    reply_markup=after_delete_keyboard(period),
                )
            else:
                # Нет прав / другая ошибка API — статус не меняем,
                # пост остаётся в списке, чтобы можно было повторить
                await callback.message.answer(
                    "❌ Не удалось удалить сообщение.\n"
                    "Проверьте права бота в канале "
                    "(нужно право удалять сообщения) и попробуйте снова.",
                    reply_markup=after_delete_keyboard(period),
                )
            return
        except Exception as exc:
            logger.exception(
                "Ошибка удаления поста %s (message_id=%s)",
                post.id,
                post.telegram_message_id,
            )
            if _is_message_already_gone(exc):
                await repo.mark_deleted(post_id, deleted_at=get_local_now())
                await callback.message.answer(
                    "ℹ️ Сообщение уже было удалено из канала.\n"
                    "Запись обновлена и больше не отображается в «🗑 Посты».",
                    reply_markup=after_delete_keyboard(period),
                )
            else:
                await callback.message.answer(
                    "❌ Не удалось удалить сообщение.\n"
                    "Попробуйте ещё раз позже.",
                    reply_markup=after_delete_keyboard(period),
                )
            return

        await repo.mark_deleted(post_id, deleted_at=get_local_now())

    await callback.message.answer(
        "✅ Пост успешно удалён.",
        reply_markup=after_delete_keyboard(period),
    )
