from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import show_preview
from services.scheduled_publisher import get_local_now
from states.post import CreatePost
from keyboards.menu import main_menu

router = Router()


def _post_title(post) -> str:
    if post.text:
        title = post.text.replace("\n", " ").strip()
        if len(title) > 28:
            title = title[:28] + "..."
        return title
    if post.media:
        return "🖼 Фото"
    return f"Пост #{post.id}"


def _group_history(posts):
    now = get_local_now().date()
    today = []
    yesterday = []
    earlier = []
    for post in posts:
        day = (post.created_at or datetime.utcnow()).date()
        if day == now:
            today.append(post)
        elif day == now - timedelta(days=1):
            yesterday.append(post)
        else:
            earlier.append(post)
    return today, yesterday, earlier


def _history_keyboard(posts) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    today, yesterday, earlier = _group_history(posts)

    def add_section(label: str, items):
        if not items:
            return
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"—— {label} ——",
                    callback_data="hist_noop",
                )
            ]
        )
        for post in items:
            if post.status == "failed":
                prefix = "❌"
            elif post.status == "deleted":
                prefix = "🗑 Удалён ·"
            else:
                prefix = "✅"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{prefix} {_post_title(post)}",
                        callback_data=f"hist_open:{post.id}",
                    )
                ]
            )

    add_section("Сегодня", today)
    add_section("Вчера", yesterday)
    add_section("Ранее", earlier)
    rows.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="hist_to_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_post_keyboard(post_id: int, status: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="👁 Открыть содержимое",
                callback_data=f"hist_view:{post_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Дублировать",
                callback_data=f"dup_post:{post_id}",
            )
        ],
    ]
    if status == "failed":
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔄 Повторить публикацию",
                    callback_data=f"hist_retry:{post_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="hist_back",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)



@router.message(F.text == "📚 История")
async def history_list(message: Message):
    if message.from_user is None:
        return

    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_history(message.from_user.id)

    if not posts:
        await message.answer(
            "📚 История пуста.\nОпубликованные посты появятся здесь.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🏠 Главное меню",
                            callback_data="hist_to_menu",
                        )
                    ]
                ]
            ),
        )
        return

    await message.answer(
        f"📚 <b>История</b>\n\nВсего: <b>{len(posts)}</b>",
        parse_mode="HTML",
        reply_markup=_history_keyboard(posts),
    )


@router.callback_query(F.data == "hist_to_menu")
async def history_to_menu(callback: CallbackQuery):
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu,
        )


@router.callback_query(F.data == "hist_noop")
async def history_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "hist_back")
async def history_back(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_history(callback.from_user.id)

    if not posts:
        await callback.message.answer(
            "📚 История пуста.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🏠 Главное меню",
                            callback_data="hist_to_menu",
                        )
                    ]
                ]
            ),
        )
        return

    await callback.message.answer(
        f"📚 <b>История</b>\n\nВсего: <b>{len(posts)}</b>",
        parse_mode="HTML",
        reply_markup=_history_keyboard(posts),
    )


@router.callback_query(F.data.startswith("hist_open:"))
async def history_open(callback: CallbackQuery):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    if callback.from_user is None:
        return

    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != callback.from_user.id:
        await callback.message.answer("❌ Пост не найден.")
        return

    if post.status == "deleted":
        if post.deleted_at:
            status_block = (
                f"Статус: <b>🗑 Удалён</b>\n"
                f"{post.deleted_at.strftime('%d.%m.%Y %H:%M')}"
            )
        else:
            status_block = "Статус: <b>🗑 Удалён</b>"
        extra = ""
    elif post.status == "failed":
        status_block = "Статус: <b>❌ ошибка</b>"
        extra = ""
        if post.error_message:
            extra = f"\n\n⚠️ {post.error_message}"
    else:
        status_block = "Статус: <b>✅ опубликован</b>"
        extra = ""

    await callback.message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await callback.message.answer(
        f"📚 <b>Пост №{post.id}</b>\n"
        f"{status_block}\n"
        f"{_post_title(post)}{extra}",
        parse_mode="HTML",
        reply_markup=history_post_keyboard(post.id, post.status),
    )


@router.callback_query(F.data.startswith("hist_view:"))
async def history_view(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    if callback.from_user is None:
        return

    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != callback.from_user.id:
        await callback.message.answer("❌ Пост не найден.")
        return

    await state.clear()
    await state.update_data(post_id=post_id)
    await state.set_state(CreatePost.preview)
    await show_preview(callback, state)


@router.callback_query(F.data.startswith("hist_retry:"))
async def history_retry(callback: CallbackQuery, state: FSMContext):
    """Перенаправляем на единый retry_publish."""
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    # Эмулируем callback retry_publish:{id}
    callback.data = f"retry_publish:{post_id}"
    from handlers.post.publish import retry_publish
    await retry_publish(callback, state)
