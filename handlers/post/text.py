from aiogram import Router
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


@router.message(CreatePost.waiting_text)
async def save_text(
    message: Message,
    state: FSMContext,
):

    if message.text is None:
        await message.answer(
            "❌ Не удалось получить текст сообщения."
        )
        return

    data = await state.get_data()

    post_id = data["post_id"]

    async with AsyncSessionLocal() as session:

        repo = PostRepository(session)

        await repo.update_text(
            post_id=post_id,
            text=message.text,
        )

    await state.update_data(
        post_id=post_id,
        original_text=message.text,
    )

    await state.set_state(
        CreatePost.formatting
    )

    await message.answer(
        HUB_TEXT,
        reply_markup=formatting_keyboard,
    )
