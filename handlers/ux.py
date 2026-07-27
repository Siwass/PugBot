"""Общие callback'и UX: главное меню, черновики."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.post.preview_service import show_draft_list
from keyboards.menu import main_menu

router = Router(name="ux")


@router.callback_query(F.data == "ux_to_menu")
async def ux_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu,
        )


@router.callback_query(F.data == "ux_open_drafts")
async def ux_open_drafts(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None:
        return
    await state.clear()
    await show_draft_list(
        callback,
        author_id=callback.from_user.id,
        restore_main_menu=False,
    )
