from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from services.channel_access import user_owns_channel_id
from database.post_repository import PostRepository
from database.user_settings_repository import UserSettingsRepository
from states.post import CreatePost

router = Router()


def new_post_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Создать с нуля",
                    callback_data="new_post_blank",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Использовать шаблон",
                    callback_data="new_post_from_template",
                )
            ],
        ]
    )


@router.message(F.text == "📝 Новый пост")
async def new_post(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📝 <b>Новый пост</b>\n\n"
        "Как хотите начать?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Выберите способ:",
        reply_markup=new_post_start_keyboard(),
    )


@router.callback_query(F.data == "new_post_blank")
async def new_post_blank(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None:
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        settings_repo = UserSettingsRepository(session)

        post = await repo.create(author_id=callback.from_user.id)

        settings = await settings_repo.get(callback.from_user.id)
        if settings and settings.default_channel_id:
            if await user_owns_channel_id(
                callback.from_user.id, settings.default_channel_id
            ):
                await repo.update_channel(post.id, settings.default_channel_id)
        if settings and settings.default_auto_delete_hours:
            await repo.set_auto_delete(
                post.id, settings.default_auto_delete_hours
            )

        post_id = post.id

    await state.clear()
    await state.update_data(post_id=post_id)
    await state.set_state(CreatePost.waiting_text)

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"📝 Черновик №{post_id} создан.\n\n"
            "✍️ Теперь отправьте текст публикации.",
            reply_markup=ReplyKeyboardRemove(),
        )
