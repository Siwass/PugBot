from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from database.db import AsyncSessionLocal
from services.channel_access import CHANNEL_ACCESS_DENIED_TEXT, user_owns_channel_id
from database.post_repository import PostRepository
from handlers.post.preview_service import QUEUE_NOT_SCHEDULED_MESSAGE
from handlers.post.schedule_service import (
    SCHEDULE_CONTEXT_NEW,
    SCHEDULE_CONTEXT_QUEUE,
    SCHEDULE_INPUT_FULL,
    SCHEDULE_INPUT_TIME_ONLY,
    cancel_schedule_wizard,
    complete_schedule_wizard,
    finalize_scheduled_post,
    schedule_date_from_offset,
    combine_publish_at,
    validate_future_publish_at,
)
from keyboards.schedule_picker import schedule_date_keyboard, schedule_time_keyboard
from states.post import CreatePost

router = Router()


async def start_schedule_wizard(
    target: Message | CallbackQuery,
    state: FSMContext,
    *,
    post_id: int,
    schedule_context: str,
) -> None:
    await state.update_data(
        post_id=post_id,
        schedule_context=schedule_context,
        schedule_input_mode=None,
        schedule_selected_date=None,
        pending_publish_at=None,
    )
    await state.set_state(CreatePost.choosing_schedule_date)

    text = "📅 <b>Выберите дату</b>"
    markup = schedule_date_keyboard()

    if isinstance(target, CallbackQuery):
        if target.message is None:
            return
        await target.message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer("👇", reply_markup=ReplyKeyboardRemove())
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


async def show_time_step(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await state.set_state(CreatePost.choosing_schedule_time)
    await callback.message.answer(
        "🕒 <b>Выберите время</b>",
        reply_markup=schedule_time_keyboard(),
        parse_mode="HTML",
    )


async def show_time_step_message(message: Message, state: FSMContext) -> None:
    await state.set_state(CreatePost.choosing_schedule_time)
    await message.answer(
        "🕒 <b>Выберите время</b>",
        reply_markup=schedule_time_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    CreatePost.choosing_schedule_date,
    F.data.startswith("sch_pick_date:"),
)
async def pick_schedule_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.data is None or callback.message is None:
        return

    raw = callback.data.removeprefix("sch_pick_date:")
    if raw == "other":
        await state.set_state(CreatePost.waiting_schedule)
        await state.update_data(schedule_input_mode=SCHEDULE_INPUT_FULL)
        await callback.message.answer(
            "📅 Введите дату и время публикации.\n\n"
            "Время указывается по Киеву.\n\n"
            "Примеры:\n"
            "сегодня 18:30\n"
            "завтра 09:00\n"
            "30.07 14:20\n"
            "24.07.2026 18:30",
        )
        return

    try:
        day_offset = int(raw)
    except ValueError:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    if day_offset not in (0, 1, 2):
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    selected = schedule_date_from_offset(day_offset)
    await state.update_data(
        schedule_selected_date=selected.isoformat(),
        schedule_input_mode=None,
    )
    await show_time_step(callback, state)


@router.callback_query(
    CreatePost.choosing_schedule_time,
    F.data.startswith("sch_pick_time:"),
)
async def pick_schedule_time(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    raw = callback.data.removeprefix("sch_pick_time:")

    if raw == "manual":
        await callback.answer()
        data = await state.get_data()
        selected_date_raw = data.get("schedule_selected_date")
        if not selected_date_raw:
            await callback.message.answer("❌ Сначала выберите дату.")
            return

        await state.set_state(CreatePost.waiting_schedule)
        await state.update_data(schedule_input_mode=SCHEDULE_INPUT_TIME_ONLY)
        await callback.message.answer(
            "✏️ Введите время публикации.\n\n"
            "Время указывается по Киеву.\n\n"
            "Примеры:\n"
            "18:30\n"
            "09:00",
        )
        return

    await callback.answer()

    time_label = raw.replace("-", ":")
    data = await state.get_data()
    selected_date_raw = data.get("schedule_selected_date")

    if not selected_date_raw:
        await callback.message.answer("❌ Сначала выберите дату.")
        return

    try:
        selected_date = date.fromisoformat(selected_date_raw)
        parsed_time = datetime.strptime(time_label, "%H:%M").time()
    except ValueError:
        await callback.answer("❌ Некорректное время.", show_alert=True)
        return

    publish_at = combine_publish_at(selected_date, parsed_time)

    if not validate_future_publish_at(publish_at):
        await callback.message.answer(
            "❌ Это время уже прошло.\n\n"
            "Выберите другое время или введите время вручную.\n"
            "Время указывается по Киеву.",
            reply_markup=schedule_time_keyboard(),
        )
        return

    await complete_schedule_wizard(callback, state, publish_at)


@router.callback_query(
    CreatePost.choosing_schedule_channel,
    F.data.startswith("sch_select_channel:"),
)
async def select_schedule_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.data is None or callback.message is None:
        return

    if callback.from_user is None:
        await callback.message.answer("❌ Не удалось определить пользователя.")
        return

    try:
        _, channel_id_str, post_id_str = callback.data.split(":")
        channel_id = int(channel_id_str)
        post_id = int(post_id_str)
    except (ValueError, IndexError):
        await callback.message.answer("❌ Некорректные данные выбора канала.")
        return

    data = await state.get_data()
    pending_raw = data.get("pending_publish_at")
    if not pending_raw:
        await callback.message.answer("❌ Не найдено время публикации. Начните планирование заново.")
        return

    try:
        publish_at = datetime.fromisoformat(pending_raw)
    except ValueError:
        await callback.message.answer("❌ Некорректное время публикации.")
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

        updated = await repo.update_channel(post_id, channel_id)
        if not updated:
            await callback.message.answer("❌ Не удалось сохранить выбор канала.")
            return

    schedule_context = data.get("schedule_context", SCHEDULE_CONTEXT_NEW)

    await finalize_scheduled_post(
        callback.message,
        state,
        post_id=post_id,
        user_id=callback.from_user.id,
        publish_at=publish_at,
        schedule_context=schedule_context,
    )


@router.callback_query(F.data == "sch_wiz_back")
async def schedule_wizard_back(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка «Назад» доступна на клавиатуре выбора времени.
    После перехода в ручной ввод (waiting_schedule) старое сообщение
    с inline-кнопкой остаётся — callback должен обрабатываться и там.
    """
    current = await state.get_state()
    allowed_states = {
        CreatePost.choosing_schedule_time.state,
        CreatePost.waiting_schedule.state,
    }

    if current not in allowed_states:
        await callback.answer()
        return

    await callback.answer()

    if callback.message is None:
        return

    data = await state.get_data()
    input_mode = data.get("schedule_input_mode")
    selected_date_raw = data.get("schedule_selected_date")

    # Ручной ввод только времени → назад к выбору времени (дата уже выбрана)
    if (
        current == CreatePost.waiting_schedule.state
        and input_mode == SCHEDULE_INPUT_TIME_ONLY
        and selected_date_raw
    ):
        await state.update_data(schedule_input_mode=None)
        await show_time_step(callback, state)
        return

    # Выбор времени или полный ручной ввод даты+времени → назад к выбору даты
    await state.set_state(CreatePost.choosing_schedule_date)
    await state.update_data(
        schedule_selected_date=None,
        schedule_input_mode=None,
    )
    await callback.message.answer(
        "📅 <b>Выберите дату</b>",
        reply_markup=schedule_date_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sch_wiz_cancel")
async def schedule_wizard_cancel(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    allowed_states = {
        CreatePost.choosing_schedule_date.state,
        CreatePost.choosing_schedule_time.state,
        CreatePost.waiting_schedule.state,
        CreatePost.choosing_schedule_channel.state,
    }
    if current not in allowed_states:
        await callback.answer()
        return

    await callback.answer()
    await cancel_schedule_wizard(callback, state)


@router.callback_query(F.data == "sch_noop")
async def schedule_wizard_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("queue_time_"))
async def queue_change_time(callback: CallbackQuery, state: FSMContext):
    if callback.data is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    try:
        post_id = int(callback.data.removeprefix("queue_time_"))
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
        await callback.answer(QUEUE_NOT_SCHEDULED_MESSAGE, show_alert=True)
        return

    await callback.answer()
    await start_schedule_wizard(
        callback,
        state,
        post_id=post_id,
        schedule_context=SCHEDULE_CONTEXT_QUEUE,
    )