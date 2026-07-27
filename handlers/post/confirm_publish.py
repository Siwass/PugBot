from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.confirm_publish import confirm_publish_keyboard
from keyboards.preview import preview_keyboard
from services.channel_access import CHANNEL_ACCESS_DENIED_TEXT, user_owns_channel_id
from services.channel_resolver import get_user_channels
from states.post import CreatePost

router = Router()


async def _get_channel_selection_keyboard(user_id: int, post_id: int) -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора канала"""
    channels = await get_user_channels(user_id)
    buttons = []
    for channel in channels:
        text = f"📺 {channel.title or 'Канал'}"
        callback_data = f"select_channel:{channel.id}:{post_id}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_publish")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "publish")
async def confirm_publish(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Не удалось найти черновик.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post or post.author_id != callback.from_user.id:
            await callback.message.answer("❌ Пост не найден.")
            return

    user_channels = await get_user_channels(callback.from_user.id)

    if len(user_channels) <= 1:
        await callback.message.answer(
            "⚠️ <b>Подтверждение публикации</b>\n\n"
            "Вы уверены, что хотите опубликовать этот пост?\n\n"
            "После подтверждения сообщение будет отправлено в канал.",
            reply_markup=confirm_publish_keyboard,
            parse_mode="HTML",
        )
        return

    keyboard = await _get_channel_selection_keyboard(callback.from_user.id, post_id)
    await callback.message.answer(
        "📺 <b>Выберите канал для публикации</b>\n\n"
        "В какой канал отправить этот пост?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("select_channel:"))
async def select_channel_for_post(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    try:
        _, channel_id_str, post_id_str = callback.data.split(":")
        channel_id = int(channel_id_str)
        post_id = int(post_id_str)
    except (ValueError, IndexError):
        await callback.message.answer("❌ Некорректные данные выбора канала.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post or post.author_id != callback.from_user.id:
            await callback.message.answer("❌ Пост не найден.")
            return

        if not await user_owns_channel_id(callback.from_user.id, channel_id):
            await callback.message.answer(
                CHANNEL_ACCESS_DENIED_TEXT,
                parse_mode="HTML",
            )
            return

        updated_post = await repo.update_channel(post_id, channel_id)
        if not updated_post:
            await callback.message.answer("❌ Не удалось сохранить выбор канала.")
            return

    await callback.message.answer(
        "✅ Канал выбран. Переходим к подтверждению...",
        parse_mode="HTML",
    )

    await callback.message.answer(
        "⚠️ <b>Подтверждение публикации</b>\n\n"
        "Вы уверены, что хотите опубликовать этот пост?\n\n"
        "После подтверждения сообщение будет отправлено в выбранный канал.",
        reply_markup=confirm_publish_keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel_publish")
async def cancel_publish(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "👀 <b>Предпросмотр</b>\n\n"
        "Выберите действие:",
        reply_markup=preview_keyboard,
        parse_mode="HTML",
    )

@router.callback_query(F.data == "preview")
async def preview_from_edit_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    post_id = data.get("post_id")
    if post_id:
        await state.update_data(post_id=post_id)
        await state.set_state(CreatePost.preview)
    from handlers.post.preview_service import show_preview
    await show_preview(callback, state)
