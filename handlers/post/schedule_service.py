from datetime import date, datetime, time, timedelta

from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import show_queue_preview
from keyboards.menu import main_menu
from keyboards.schedule import schedule_keyboard
from services.channel_resolver import get_user_channels
from services.scheduled_publisher import get_local_now
from states.post import CreatePost

SCHEDULE_CONTEXT_NEW = "new"
SCHEDULE_CONTEXT_QUEUE = "queue"

SCHEDULE_INPUT_FULL = "full"
SCHEDULE_INPUT_TIME_ONLY = "time_only"


async def resolve_user_now(user_id: int | None = None) -> datetime:
    """Локальное «сейчас» с учётом пояса пользователя."""
    if user_id is None:
        return get_local_now()
    try:
        from database.user_settings_repository import UserSettingsRepository
        async with AsyncSessionLocal() as session:
            settings = await UserSettingsRepository(session).get(user_id)
            tz_name = settings.timezone if settings else None
        from utils.timezones import get_user_now
        return get_user_now(tz_name)
    except Exception:
        return get_local_now()




def schedule_date_from_offset(day_offset: int) -> date:
    return get_local_now().date() + timedelta(days=day_offset)


def combine_publish_at(selected_date: date, selected_time: time) -> datetime:
    return datetime.combine(selected_date, selected_time)


def parse_manual_publish_at(
    text: str,
    *,
    selected_date: date | None,
    input_mode: str,
) -> datetime | None:
    """Parse flexible schedule input.

    Supported examples:
    - 18:30              (time only; uses selected_date or today)
    - сегодня 18:30 / Сегодня 18:30
    - завтра 09:00
    - послезавтра 14:20
    - 30.07 14:20        (day.month, current year)
    - 30.07.2026 14:20
    - 24.07.2026 18:30
    """
    import re

    raw = text.strip()
    if not raw:
        return None

    lowered = raw.lower()
    now = get_local_now()
    base_date: date | None = selected_date

    # Relative day keywords
    relative_map = {
        "сегодня": 0,
        "завтра": 1,
        "послезавтра": 2,
    }
    for word, offset in relative_map.items():
        if lowered.startswith(word):
            base_date = schedule_date_from_offset(offset)
            # strip keyword and optional separators
            rest = raw[len(word):].strip(" ,.-")
            raw = rest if rest else raw
            lowered = raw.lower()
            break

    # Time-only: HH:MM (or H:MM)
    time_only = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
    if time_only:
        try:
            h, m = int(time_only.group(1)), int(time_only.group(2))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return None
            parsed_time = time(h, m)
        except ValueError:
            return None
        if base_date is None:
            if input_mode == SCHEDULE_INPUT_TIME_ONLY and selected_date is not None:
                base_date = selected_date
            else:
                base_date = now.date()
        return combine_publish_at(base_date, parsed_time)

    # DD.MM HH:MM (current year)
    m_dm = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})", raw)
    if m_dm:
        try:
            d, mo = int(m_dm.group(1)), int(m_dm.group(2))
            h, mi = int(m_dm.group(3)), int(m_dm.group(4))
            if not (0 <= h <= 23 and 0 <= mi <= 59):
                return None
            year = now.year
            candidate = datetime(year, mo, d, h, mi)
            # if already past this year and looks intentional for next year
            if candidate <= now and (mo, d) < (now.month, now.day):
                candidate = datetime(year + 1, mo, d, h, mi)
            return candidate
        except ValueError:
            return None

    # DD.MM.YYYY HH:MM
    try:
        return datetime.strptime(raw, "%d.%m.%Y %H:%M")
    except ValueError:
        pass

    # If relative keyword left only time already handled; fallback None
    return None


def validate_future_publish_at(publish_at: datetime) -> bool:
    return publish_at > get_local_now()


def schedule_channel_keyboard(channels, post_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for channel in channels:
        text = f"📺 {channel.title or 'Канал'}"
        callback_data = f"sch_select_channel:{channel.id}:{post_id}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    buttons.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="sch_wiz_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def persist_publish_at(
    *,
    post_id: int,
    user_id: int,
    publish_at: datetime,
    schedule_context: str,
) -> tuple[bool, str | None]:
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or post.author_id != user_id:
            return False, "❌ Пост не найден."

        if schedule_context == SCHEDULE_CONTEXT_QUEUE:
            if post.status != "scheduled":
                return False, "❌ Пост больше не в очереди."

            updated = await repo.update_publish_time(
                post_id=post_id,
                publish_at=publish_at,
            )
            if not updated:
                return False, "❌ Не удалось изменить время публикации."
            return True, None

        scheduled_post = await repo.schedule_post(
            post_id=post_id,
            publish_at=publish_at,
        )
        if not scheduled_post:
            return False, "❌ Не удалось запланировать пост."
        return True, None


async def cancel_schedule_wizard(
    target: Message | CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    schedule_context = data.get("schedule_context", SCHEDULE_CONTEXT_NEW)
    post_id = data.get("post_id")

    await state.update_data(
        schedule_context=None,
        schedule_input_mode=None,
        schedule_selected_date=None,
        pending_publish_at=None,
    )

    if schedule_context == SCHEDULE_CONTEXT_QUEUE and post_id:
        await state.set_state(CreatePost.preview)
        await state.update_data(post_id=post_id)
        # Возврат к превью очереди без новых сообщений
        await show_queue_preview(target, state)
        return

    # Возврат на главный экран управления публикацией
    await state.set_state(CreatePost.formatting)
    if isinstance(target, Message):
        message = target
    elif isinstance(target.message, Message):
        message = target.message
    else:
        return
    from keyboards.formatting import formatting_keyboard
    await message.answer(
        "↩️ Планирование отменено.\n\n"
        "Что хотите сделать дальше?",
        reply_markup=formatting_keyboard,
    )


async def finalize_scheduled_post(
    message: Message,
    state: FSMContext,
    *,
    post_id: int,
    user_id: int,
    publish_at: datetime,
    schedule_context: str,
) -> None:
    ok, error = await persist_publish_at(
        post_id=post_id,
        user_id=user_id,
        publish_at=publish_at,
        schedule_context=schedule_context,
    )

    if not ok:
        await message.answer(error or "❌ Не удалось сохранить время публикации.")
        return

    formatted = publish_at.strftime("%d.%m.%Y %H:%M")

    if schedule_context == SCHEDULE_CONTEXT_QUEUE:
        await state.set_state(CreatePost.preview)
        await state.update_data(
            post_id=post_id,
            schedule_context=None,
            schedule_input_mode=None,
            schedule_selected_date=None,
            pending_publish_at=None,
        )
        # Обновляем то же сообщение: превью поста с новым временем
        await show_queue_preview(message, state)
        return

    await state.clear()
    await message.answer(
        "✅ Пост успешно добавлен в очередь.\n\n"
        f"🕒 {formatted} (Киев)",
        reply_markup=main_menu,
    )


async def complete_schedule_wizard(
    target: Message | CallbackQuery,
    state: FSMContext,
    publish_at: datetime,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
    schedule_context = data.get("schedule_context", SCHEDULE_CONTEXT_NEW)

    if isinstance(target, Message):
        message: Message = target
    else:
        if not isinstance(target.message, Message):
            return
        message = target.message

    if not post_id:
        await message.answer("❌ Не удалось найти пост.")
        return

    if target.from_user is None:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = target.from_user.id

    # Для новой отложки — выбор канала (как при мгновенной публикации)
    if schedule_context == SCHEDULE_CONTEXT_NEW:
        user_channels = await get_user_channels(user_id)

        if len(user_channels) > 1:
            await state.update_data(
                pending_publish_at=publish_at.isoformat(),
            )
            await state.set_state(CreatePost.choosing_schedule_channel)
            await message.answer(
                "📺 <b>Выберите канал для публикации</b>\n\n"
                "В какой канал запланировать этот пост?",
                reply_markup=schedule_channel_keyboard(user_channels, post_id),
                parse_mode="HTML",
            )
            return

        if len(user_channels) == 1:
            async with AsyncSessionLocal() as session:
                repo = PostRepository(session)
                await repo.update_channel(post_id, user_channels[0].id)

    await finalize_scheduled_post(
        message,
        state,
        post_id=post_id,
        user_id=user_id,
        publish_at=publish_at,
        schedule_context=schedule_context,
    )