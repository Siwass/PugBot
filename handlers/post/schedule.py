from datetime import date

from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from handlers.post.schedule_service import (
    SCHEDULE_CONTEXT_NEW,
    SCHEDULE_INPUT_FULL,
    SCHEDULE_INPUT_TIME_ONLY,
    complete_schedule_wizard,
    parse_manual_publish_at,
    validate_future_publish_at,
)
from handlers.post.schedule_wizard import start_schedule_wizard
from states.post import CreatePost

router = Router()


@router.message(
    CreatePost.waiting_schedule_choice,
    F.text == "📅 Запланировать",
)
async def schedule_choose(message: Message, state: FSMContext):

    data = await state.get_data()
    post_id = data.get("post_id")

    if not post_id:
        await message.answer("❌ Не удалось найти черновик.")
        return

    await start_schedule_wizard(
        message,
        state,
        post_id=post_id,
        schedule_context=SCHEDULE_CONTEXT_NEW,
    )


@router.message(CreatePost.waiting_schedule, F.text)
async def save_schedule(message: Message, state: FSMContext):

    if message.text is None:
        await message.answer("❌ Не удалось получить текст.")
        return

    data = await state.get_data()
    input_mode = data.get("schedule_input_mode", SCHEDULE_INPUT_FULL)
    selected_date_raw = data.get("schedule_selected_date")

    selected_date = None
    if selected_date_raw:
        try:
            selected_date = date.fromisoformat(selected_date_raw)
        except ValueError:
            selected_date = None

    publish_at = parse_manual_publish_at(
        message.text,
        selected_date=selected_date,
        input_mode=input_mode,
    )

    if publish_at is None:
        if input_mode == SCHEDULE_INPUT_TIME_ONLY:
            await message.answer(
                "❌ Неверный формат.\n\n"
                "Примеры:\n"
                "18:30\n"
                "09:00"
            )
        else:
            await message.answer(
                "❌ Неверный формат.\n\n"
                "Примеры:\n"
                "сегодня 18:30\n"
                "завтра 09:00\n"
                "30.07 14:20\n"
                "24.07.2026 18:30"
            )
        return

    if not validate_future_publish_at(publish_at):
        if input_mode == SCHEDULE_INPUT_TIME_ONLY:
            await message.answer(
                "❌ Это время уже прошло.\n\n"
                "Введите другое время (по Киеву) или нажмите «⬅️ Назад» "
                "на предыдущем сообщении, чтобы выбрать время из списка.\n\n"
                "Примеры:\n"
                "18:30\n"
                "09:00"
            )
            return

        await message.answer(
            "❌ Укажите дату и время в будущем.\n\n"
            "Время указывается по Киеву.\n\n"
            "Примеры:\n"
            "сегодня 18:30\n"
            "завтра 09:00\n"
            "30.07 14:20"
        )
        return

    await complete_schedule_wizard(message, state, publish_at)