import json
import logging
from contextlib import suppress

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.models import Post
from database.post_repository import PostRepository
from keyboards.preview import preview_keyboard
from keyboards.queue_preview import queue_preview_keyboard
from keyboards.draft_preview import draft_preview_keyboard
from keyboards.menu import main_menu
from services.publishing import answer_photo_with_text
from states.post import CreatePost

logger = logging.getLogger(__name__)

EDIT_CONTEXT_QUEUE = "queue"
EDIT_CONTEXT_DRAFT = "draft"

def _autodel_preview_line(post: Post) -> str:
    """Строка для карточки предпросмотра."""
    hours = post.auto_delete_hours
    if hours is None:
        return "⏳ Автоудаление\n\nОтключено"
    return f"⏳ Автоудаление\n\nДля этого поста:\n\n{hours} часов"


QUEUE_NOT_SCHEDULED_MESSAGE = (
    "❌ Пост больше не в очереди: статус уже изменился "
    "(публикуется, опубликован или снят с расписания). "
    "Откройте 📅 Очередь заново."
)


def _target_message(target: Message | CallbackQuery) -> Message:
    if isinstance(target, CallbackQuery):
        return target.message
    # duck-typing for tests / partial objects
    msg = getattr(target, "message", None)
    if msg is not None and getattr(target, "data", None) is not None:
        return msg
    return target


def _post_url_button_rows(post: Post) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []

    if post.buttons:
        try:
            buttons = json.loads(post.buttons)
        except (json.JSONDecodeError, TypeError):
            buttons = []

        for button in buttons:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button["text"],
                        url=button["url"],
                    )
                ]
            )

    return rows


def _queue_post_title(post: Post) -> str:
    if post.text:
        title = post.text.replace("\n", " ")
        for tag in ("<b>", "</b>", "<i>", "</i>", "<u>", "</u>", "<s>", "</s>"):
            title = title.replace(tag, "")
        while "<a " in title and "</a>" in title:
            start = title.find("<a ")
            mid = title.find(">", start)
            end = title.find("</a>", mid)
            if start == -1 or mid == -1 or end == -1:
                break
            title = title[:start] + title[mid + 1:end] + title[end + 4:]
        title = title.strip()
        if len(title) > 30:
            title = title[:30] + "..."
        return title or "📝 Без текста"
    if post.media:
        return "🖼 Фото"
    return "📝 Без текста"


def _queue_list_keyboard(posts: list[Post]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for post in posts:
        title = _queue_post_title(post)
        time_str = (
            post.publish_at.strftime("%d.%m %H:%M")
            if post.publish_at
            else "??.?? ??:??"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🕒 {time_str} | {title}",
                    callback_data=f"queue_{post.id}",
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="queue_to_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _load_post(post_id: int) -> Post | None:
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        return await repo.get_by_id(post_id)


async def safe_edit_text(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> bool:
    """Редактирует текст сообщения; при ошибке отправляет новое."""
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramBadRequest as exc:
        logger.debug("safe_edit_text: edit failed (%s), fallback to answer", exc)
        with suppress(Exception):
            await message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        return False
    except Exception:
        logger.exception("safe_edit_text: unexpected error")
        with suppress(Exception):
            await message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        return False


async def show_queue_list(
    target: Message | CallbackQuery,
    *,
    author_id: int,
    restore_main_menu: bool = False,
) -> None:
    """Показать/обновить список очереди публикаций.

    restore_main_menu=True — вернуть ReplyKeyboard главного меню
    (после выхода из карточки поста).
    """
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_scheduled_posts(author_id=author_id)

    if not posts:
        text = "📅 Очередь публикаций пуста."
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="queue_to_menu",
                    )
                ]
            ]
        )
    else:
        text = (
            f"📅 <b>Очередь публикаций</b>\n\n"
            f"Всего: <b>{len(posts)}</b>"
        )
        markup = _queue_list_keyboard(posts)

    if isinstance(target, CallbackQuery):
        message = target.message
        if message is None:
            return
        if restore_main_menu:
            # edit_text не меняет ReplyKeyboard — шлём отдельное сообщение
            await message.answer(text, parse_mode="HTML", reply_markup=main_menu)
            if markup is not None:
                await message.answer("Выберите пост:", reply_markup=markup)
            return
        await safe_edit_text(message, text, reply_markup=markup)
        return

    kb = main_menu if restore_main_menu else None
    await target.answer(text, parse_mode="HTML", reply_markup=kb or markup)
    if restore_main_menu and markup is not None:
        await target.answer("Выберите пост:", reply_markup=markup)


async def _send_post_preview(
    message: Message,
    post: Post,
    keyboard: InlineKeyboardMarkup,
) -> None:
    if post.status == "scheduled" and post.publish_at:
        header_parts = [
            f"📅 <b>Пост в очереди №{post.id}</b>",
            f"🕒 {post.publish_at.strftime('%d.%m.%Y %H:%M')} (Киев)",
        ]
    else:
        header_parts = [f"👀 <b>Предпросмотр №{post.id}</b>"]
    header_parts.append("")
    header_parts.append(_autodel_preview_line(post))
    header = "\n".join(header_parts)

    await message.answer(header, parse_mode="HTML")

    text = post.text or ""

    if post.media:
        try:
            media = json.loads(post.media)
        except (json.JSONDecodeError, TypeError):
            media = None

        if media and media.get("type") == "photo" and media.get("files"):
            try:
                await answer_photo_with_text(
                    message,
                    media["files"][0],
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception(
                    "Не удалось отправить фото превью поста %s", post.id
                )
                await message.answer(
                    (text or "Без текста")
                    + "\n\n📷 <i>Медиа прикреплено к посту</i>",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            return

    await message.answer(
        text or "Без текста",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def show_preview(
    target: Message | CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")

    if not post_id:
        return

    post = await _load_post(post_id)

    if not post:
        return

    inline_buttons = _post_url_button_rows(post)
    inline_buttons.extend(preview_keyboard.inline_keyboard)

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    await _send_post_preview(_target_message(target), post, keyboard)


async def show_queue_preview(
    target: Message | CallbackQuery,
    state: FSMContext,
    *,
    post_id: int | None = None,
) -> None:
    if post_id is None:
        data = await state.get_data()
        post_id = data.get("post_id")

    if not post_id:
        msg = _target_message(target)
        if msg:
            await msg.answer("❌ Не удалось определить пост.")
        return

    post = await _load_post(post_id)

    if not post:
        msg = _target_message(target)
        if msg:
            await msg.answer("❌ Пост не найден.")
        return

    if post.status != "scheduled":
        msg = _target_message(target)
        if msg:
            await msg.answer(QUEUE_NOT_SCHEDULED_MESSAGE)
        return

    inline_buttons = _post_url_button_rows(post)
    inline_buttons.extend(queue_preview_keyboard(post_id).inline_keyboard)

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    message = _target_message(target)
    if message is None:
        return

    # Скрыть главное меню бота на время работы с карточкой
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    await _send_post_preview(message, post, keyboard)


def _draft_list_keyboard(posts: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for post in posts:
        title = (post.text or "").replace("\n", " ").strip()
        if len(title) > 30:
            title = title[:30] + "..."
        if not title:
            title = "🖼 Фото без текста" if post.media else "📝 Новый черновик"
        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"draft_open_{post.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить все",
                callback_data="delete_all_drafts",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="drafts_to_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_draft_list(
    target: Message | CallbackQuery,
    *,
    author_id: int,
    restore_main_menu: bool = False,
) -> None:
    """Показать список черновиков."""
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_drafts(author_id=author_id)

    if not posts:
        text = "📂 Черновиков пока нет."
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="drafts_to_menu",
                    )
                ]
            ]
        )
    else:
        text = (
            f"📂 <b>Черновики</b>\n\n"
            f"Всего: <b>{len(posts)}</b>\n\n"
            f"Выберите нужный:"
        )
        markup = _draft_list_keyboard(posts)

    if isinstance(target, CallbackQuery):
        message = target.message
        if message is None:
            return
        if restore_main_menu:
            await message.answer(text, parse_mode="HTML", reply_markup=main_menu)
            if markup is not None and posts:
                await message.answer("Выберите черновик:", reply_markup=markup)
            elif markup is not None:
                await message.answer(text, reply_markup=markup)
            return
        await message.answer(text, parse_mode="HTML", reply_markup=markup)
        return

    if restore_main_menu:
        await target.answer(text, parse_mode="HTML", reply_markup=main_menu)
        if markup is not None and posts:
            await target.answer("Выберите черновик:", reply_markup=markup)
        return

    await target.answer(text, parse_mode="HTML", reply_markup=markup)


async def show_draft_preview(
    target: Message | CallbackQuery,
    state: FSMContext,
    *,
    post_id: int | None = None,
) -> None:
    """Карточка черновика: контент + единые кнопки действий."""
    data = await state.get_data()
    pid = post_id or data.get("post_id")
    if not pid:
        return

    post = await _load_post(int(pid))
    if not post:
        message = _target_message(target)
        if message is not None:
            await message.answer("❌ Черновик не найден.")
        return

    if post.status != "draft":
        message = _target_message(target)
        if message is not None:
            await message.answer(
                f"ℹ️ Этот пост уже не черновик (статус: {post.status})."
            )
        return

    await state.update_data(
        post_id=post.id,
        original_text=post.text or "",
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await state.set_state(CreatePost.preview)

    keyboard = draft_preview_keyboard(post.id)
    message = _target_message(target)
    if message is None:
        return

    # Скрыть главное меню на время работы с карточкой
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    header = (
        f"📂 <b>Черновик №{post.id}</b>\n\n"
        + _autodel_preview_line(post)
    )
    await message.answer(header, parse_mode="HTML")

    text = post.text or ""
    if post.media:
        try:
            media = json.loads(post.media)
        except (json.JSONDecodeError, TypeError):
            media = None
        if media and media.get("type") == "photo" and media.get("files"):
            try:
                await answer_photo_with_text(
                    message,
                    media["files"][0],
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except Exception:
                logger.exception(
                    "Не удалось отправить фото превью черновика %s", post.id
                )
                await message.answer(
                    (text or "Без текста")
                    + "\n\n📷 <i>Медиа прикреплено к посту</i>",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return

    await message.answer(
        text or "Без текста",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
