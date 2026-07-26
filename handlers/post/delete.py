from aiogram import Router, F
from aiogram.types import CallbackQuery

from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.confirm_delete import confirm_delete_keyboard
from keyboards.menu import main_menu

router = Router()


@router.callback_query(F.data == "delete")
async def delete_post(callback: CallbackQuery):

    await callback.answer()

    await callback.message.answer(
        "⚠️ <b>Удаление поста</b>\n\n"
        "Вы уверены, что хотите удалить этот черновик?\n\n"
        "Это действие нельзя отменить.",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard,
    )


@router.callback_query(F.data == "confirm_delete")
async def confirm_delete(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    data = await state.get_data()
    post_id = data.get("post_id")

    if not post_id:
        await callback.message.answer("❌ Черновик не найден.")
        return

    async with AsyncSessionLocal() as session:

        repo = PostRepository(session)

        deleted = await repo.delete(post_id)

    if not deleted:
        await callback.message.answer("❌ Черновик уже удалён.")
        return

    await state.clear()

    await callback.message.edit_text(
        "🗑️ Черновик удалён."
    )

    await callback.message.answer(
        "✅ <b>Готово!</b>\n\n"
        "Черновик успешно удалён.\n\n"
        "Что будем делать дальше?",
        parse_mode="HTML",
        reply_markup=main_menu,
    )


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):

    await callback.answer()

    await callback.message.delete()