from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import (
    EDIT_CONTEXT_QUEUE,
    QUEUE_NOT_SCHEDULED_MESSAGE,
    show_queue_list,
    show_queue_preview,
)
from states.post import CreatePost
from keyboards.menu import main_menu

router = Router()


def _is_queue_open_callback(data: str | None) -> bool:
    """Только queue_<digits>, без queue_publish_ / queue_edit_text_ / …"""
    if not data or not data.startswith("queue_"):
        return False
    rest = data[len("queue_"):]
    return rest.isdigit()


@router.message(F.text == "📅 Очередь")
async def queue(message: Message):
    if message.from_user is None:
        return

    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_scheduled_posts(
            author_id=message.from_user.id
        )

    if not posts:
        await message.answer(
            "📅 Очередь публикаций пуста.",
            reply_markup=main_menu,
        )
        return

    keyboard = []

    for post in posts:
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
        elif post.media:
            title = "🖼 Фото"
        else:
            title = "📝 Без текста"

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

    await message.answer(
        f"📅 <b>Очередь публикаций</b>\n\n"
        f"Всего: <b>{len(posts)}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        ),
    )


@router.callback_query(F.data == "queue_to_menu")
async def queue_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu,
        )


@router.callback_query(F.data.func(_is_queue_open_callback))
async def open_queue_post(callback: CallbackQuery, state: FSMContext):
    if callback.data is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    try:
        post_id = int(callback.data.removeprefix("queue_"))
    except (TypeError, ValueError):
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    if callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != callback.from_user.id:
        await callback.answer("❌ Пост не найден.", show_alert=True)
        return

    if post.status != "scheduled":
        await callback.answer(
            QUEUE_NOT_SCHEDULED_MESSAGE,
            show_alert=True,
        )
        return

    await callback.answer()

    await state.set_state(CreatePost.preview)
    await state.update_data(
        post_id=post_id,
        edit_context=EDIT_CONTEXT_QUEUE,
    )

    await show_queue_preview(callback, state, post_id=post_id)
