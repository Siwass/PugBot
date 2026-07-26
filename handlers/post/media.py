from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from states.post import CreatePost

from keyboards.formatting import formatting_keyboard

router = Router()

HUB_TEXT = (
    "✅ Текст сохранён\n\n"
    "Что хотите сделать дальше?"
)


@router.message(CreatePost.waiting_media, F.photo)
async def save_photo(message: Message, state: FSMContext):

    data = await state.get_data()
    post_id = data["post_id"]

    file_id = message.photo[-1].file_id

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)

        await repo.update_media(
            post_id=post_id,
            media_type="photo",
            file_ids=[file_id]
        )

    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
        await state.set_state(CreatePost.preview)
        await message.answer("✅ Фото сохранено.")
        if ctx == "queue":
            from handlers.post.preview_service import show_queue_preview
            await show_queue_preview(message, state)
        else:
            from handlers.post.preview_service import show_draft_preview
            await show_draft_preview(message, state)
        return

    await state.set_state(CreatePost.formatting)
    await message.answer(
        f"✅ Фото сохранено.\n\n{HUB_TEXT}",
        reply_markup=formatting_keyboard,
    )


@router.message(CreatePost.waiting_media, F.text == "⏭ Пропустить")
async def skip_photo(message: Message, state: FSMContext):

    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
        await state.set_state(CreatePost.preview)
        await message.answer("⏭ Медиа пропущено.")
        if ctx == "queue":
            from handlers.post.preview_service import show_queue_preview
            await show_queue_preview(message, state)
        else:
            from handlers.post.preview_service import show_draft_preview
            await show_draft_preview(message, state)
        return

    await state.set_state(CreatePost.formatting)
    await message.answer(
        f"⏭ Медиа пропущено.\n\n{HUB_TEXT}",
        reply_markup=formatting_keyboard,
    )
