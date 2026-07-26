from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import (
    EDIT_CONTEXT_DRAFT,
    show_draft_preview,
)
from states.post import CreatePost
from utils.ux_errors import error_keyboard, format_error_text

router = Router()


@router.callback_query(F.data.startswith("dup_post:"))
async def duplicate_post(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.data is None or callback.from_user is None:
        return
    if not isinstance(callback.message, Message):
        return

    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer(
            format_error_text("Некорректные данные."),
            parse_mode="HTML",
            reply_markup=error_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        source = await repo.get_by_id(post_id)
        if not source or source.author_id != callback.from_user.id:
            from utils.ux_errors import STALE_MENU_TEXT, stale_menu_keyboard

            await callback.message.answer(
                STALE_MENU_TEXT,
                parse_mode="HTML",
                reply_markup=stale_menu_keyboard(),
            )
            return
        copy = await repo.duplicate(post_id, callback.from_user.id)

    if not copy:
        await callback.message.answer(
            format_error_text("Не удалось создать копию."),
            parse_mode="HTML",
            reply_markup=error_keyboard(back_callback="drafts_back"),
        )
        return

    # Снять кнопки со старого сообщения — они больше не актуальны
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.clear()
    await state.update_data(
        post_id=copy.id,
        original_text=copy.text or "",
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await state.set_state(CreatePost.preview)

    await callback.message.answer(
        f"📋 Создана копия — черновик №{copy.id}\n\n"
        "Открываю карточку нового черновика."
    )
    await show_draft_preview(callback.message, state, post_id=copy.id)
