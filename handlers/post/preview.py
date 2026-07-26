import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from states.post import CreatePost
from keyboards.preview import preview_keyboard
from services.publishing import answer_photo_with_text

router = Router()

# Варианты текста кнопки (с/без variation selector U+FE0F)
_PUBLISH_NOW_TEXTS = (
    "⚡ Опубликовать сейчас",
    "⚡️ Опубликовать сейчас",
)


@router.message(
    CreatePost.waiting_schedule_choice,
    F.text.in_(_PUBLISH_NOW_TEXTS),
)
async def preview_now(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await message.answer("❌ Черновик не найден.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post:
        await message.answer("❌ Черновик не найден.")
        return

    inline_buttons = []

    if post.buttons:
        buttons = json.loads(post.buttons)
        for button in buttons:
            inline_buttons.append(
                [
                    InlineKeyboardButton(
                        text=button["text"],
                        url=button["url"],
                    )
                ]
            )

    inline_buttons.extend(preview_keyboard.inline_keyboard)
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    await state.set_state(CreatePost.preview)

    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    if post.media:
        media = json.loads(post.media)
        if media.get("type") == "photo" and media.get("files"):
            await answer_photo_with_text(
                message,
                media["files"][0],
                post.text or "",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return

    await message.answer(
        post.text or "Без текста",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
