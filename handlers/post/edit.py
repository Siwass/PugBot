from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from database.user_settings_repository import UserSettingsRepository
from services.channel_resolver import get_user_channels
from keyboards.edit import edit_keyboard
from keyboards.formatting import formatting_keyboard
from keyboards.buttons import buttons_keyboard
from keyboards.schedule import schedule_keyboard
from states.post import CreatePost

router = Router()


@router.callback_query(F.data == "edit")
async def open_edit_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if post_id:
        await state.update_data(post_id=post_id)
        await state.set_state(CreatePost.preview)

    await callback.message.answer(
        "✏️ <b>Редактирование поста</b>\n\nВыберите, что хотите изменить:",
        reply_markup=edit_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "edit_text")
async def edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    current = ""
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if post and post.text:
            current = post.text

    await state.set_state(CreatePost.editing_text)
    await state.update_data(post_id=post_id)

    hint = f"\n\nТекущий текст:\n{current}" if current else ""
    await callback.message.answer(
        "✍️ Отправьте новый текст поста." + hint
    )


@router.message(CreatePost.editing_text)
async def save_edited_text(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Нужен текстовый ответ.")
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await message.answer("❌ Пост не найден.")
        return

    # "-" = оставить текущий текст (удобно после шаблона)
    new_text = message.text
    keep = message.text.strip() == "-"

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        if not keep:
            await repo.update_text(post_id, new_text)
            text_for_state = new_text
        else:
            post = await repo.get_by_id(post_id)
            text_for_state = (post.text if post else "") or ""

    await state.update_data(original_text=text_for_state)

    # После шаблона (флаг) идём в оформление; иначе — меню редактирования
    from_template = data.get("from_template")
    if from_template:
        await state.update_data(from_template=None)
        await state.set_state(CreatePost.formatting)
        await message.answer(
            "✅ Текст готов.\n\n"
            "🎨 Хотите оформить текст?\n\n"
            "Выберите действие:",
            reply_markup=formatting_keyboard,
        )
        return

    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
        await state.set_state(CreatePost.preview)
        await message.answer("✅ Текст обновлён.")
        if ctx == "queue":
            from handlers.post.preview_service import show_queue_preview
            await show_queue_preview(message, state)
        else:
            from handlers.post.preview_service import show_draft_preview
            await show_draft_preview(message, state)
        return

    await state.set_state(CreatePost.preview)
    await message.answer(
        "✅ Текст обновлён.\n\n"
        "✏️ <b>Редактирование поста</b>\n\nВыберите, что хотите изменить:",
        reply_markup=edit_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "edit_media")
async def edit_media(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    await state.set_state(CreatePost.editing_media)
    await state.update_data(post_id=post_id)
    await callback.message.answer(
        "🖼 Отправьте новое фото для поста.\n"
        "Или напишите «пропустить», чтобы убрать медиа."
    )


@router.message(CreatePost.editing_media, F.photo)
async def save_edited_media(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        return

    file_id = message.photo[-1].file_id
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        await repo.update_media(post_id, "photo", [file_id])

    data = await state.get_data()
    if data.get("edit_context") == "queue":
        await state.set_state(CreatePost.preview)
        from handlers.post.preview_service import show_queue_preview
        await message.answer("✅ Готово.")
        await show_queue_preview(message, state)
        return

    await state.set_state(CreatePost.preview)
    await message.answer(
        "✅ Медиа обновлено.\n\n"
        "✏️ <b>Редактирование поста</b>",
        reply_markup=edit_keyboard(),
        parse_mode="HTML",
    )


@router.message(CreatePost.editing_media, F.text)
async def clear_or_skip_media(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        return

    text = (message.text or "").lower().strip()
    if text in ("пропустить", "удалить", "без медиа", "-"):
        async with AsyncSessionLocal() as session:
            repo = PostRepository(session)
            post = await repo.get_by_id(post_id)
            if post:
                post.media = None
                await session.commit()
        await message.answer("✅ Медиа удалено.")
    else:
        await message.answer("Отправьте фото или напишите «пропустить».")
        return

    data = await state.get_data()
    if data.get("edit_context") == "queue":
        await state.set_state(CreatePost.preview)
        from handlers.post.preview_service import show_queue_preview
        await message.answer("✅ Готово.")
        await show_queue_preview(message, state)
        return

    await state.set_state(CreatePost.preview)
    await message.answer(
        "✏️ <b>Редактирование поста</b>",
        reply_markup=edit_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "edit_buttons")
async def edit_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    await state.set_state(CreatePost.waiting_buttons)
    await state.update_data(post_id=post_id)
    await callback.message.answer(
        "🔗 Редактирование кнопок.\n"
        "Можно добавить новые кнопки или нажать «Далее».",
        reply_markup=buttons_keyboard,
    )


@router.callback_query(F.data == "edit_schedule")
async def edit_schedule(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    await state.set_state(CreatePost.waiting_schedule_choice)
    await state.update_data(post_id=post_id)
    await callback.message.answer(
        "📅 Что хотите сделать?",
        reply_markup=schedule_keyboard,
    )


@router.callback_query(F.data == "edit_channel")
async def edit_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    user_id = callback.from_user.id if callback.from_user else None
    if user_id is None:
        return

    channels = await get_user_channels(user_id)

    if len(channels) <= 1:
        await callback.message.answer("✅ У вас только один канал. Смена не требуется.")
        return

    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"📺 {ch.title or 'Канал'}",
                callback_data=f"change_channel_to:{ch.id}:{post_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="edit")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.answer(
        "📺 <b>Выберите новый канал для поста</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("change_channel_to:"))
async def apply_channel_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    try:
        _, channel_id_str, post_id_str = callback.data.split(":")
        channel_id = int(channel_id_str)
        post_id = int(post_id_str)
    except Exception:
        await callback.message.answer("❌ Ошибка данных.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        updated = await repo.update_channel(post_id, channel_id)
        if not updated:
            await callback.message.answer("❌ Не удалось изменить канал.")
            return

    await state.update_data(post_id=post_id)
    await state.set_state(CreatePost.preview)

    await callback.message.answer(
        "✅ Канал успешно изменён!\n\n"
        "✏️ <b>Редактирование поста</b>\n\nВыберите, что хотите изменить:",
        reply_markup=edit_keyboard(),
        parse_mode="HTML",
    )


# ─── Автоудаление конкретного поста ─────────────────────


def _post_autodel_label(hours: int | None, *, default_hours: int | None) -> str:
    if hours is None and default_hours is None:
        return "🚫 Не удалять"
    if hours is None:
        # явно не задано на посте — показывается как «по умолчанию» только в UI выбора
        return "🚫 Не удалять"
    return f"{hours} ч"


def _post_autodel_keyboard(
    post_id: int,
    current: int | None,
    default_hours: int | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    # «По умолчанию» — сбросить к user default (применим default при выборе)
    def_mark = ""
    if default_hours is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current == default_hours else ''}По умолчанию ({default_hours} ч)",
                    callback_data=f"post_autodel:{post_id}:{default_hours}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current is None else ''}По умолчанию (выкл)",
                    callback_data=f"post_autodel:{post_id}:off",
                )
            ]
        )
    for hours in (24, 48, 72, 96):
        mark = "✅ " if current == hours else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{hours} ч",
                    callback_data=f"post_autodel:{post_id}:{hours}",
                )
            ]
        )
    off_mark = "✅ " if current is None and default_hours is not None else ""
    # «Не удалять» всегда available
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current is None else ''}🚫 Не удалять",
                callback_data=f"post_autodel:{post_id}:off",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "edit_autodel")
async def edit_autodel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    async with AsyncSessionLocal() as session:
        post = await PostRepository(session).get_by_id(post_id)
        settings = await UserSettingsRepository(session).get(callback.from_user.id)
        default_hours = settings.default_auto_delete_hours if settings else None

    if not post or post.author_id != callback.from_user.id:
        await callback.message.answer("❌ Пост не найден.")
        return

    current = post.auto_delete_hours
    if current is None and default_hours is None:
        now_label = "🚫 Не удалять"
    elif current is None:
        now_label = "🚫 Не удалять"
    elif default_hours is not None and current == default_hours:
        now_label = f"✅ По умолчанию ({default_hours} ч)"
    else:
        now_label = f"{current} ч"

    await callback.message.answer(
        "⏳ <b>Автоудаление</b>\n\n"
        f"Сейчас:\n\n"
        f"<b>{now_label}</b>\n\n"
        "────────────\n\n"
        "Выберите значение для <b>этого поста</b>:",
        parse_mode="HTML",
        reply_markup=_post_autodel_keyboard(post_id, current, default_hours),
    )


@router.callback_query(F.data.startswith("post_autodel:"))
async def apply_post_autodel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return
    try:
        _, post_id_s, raw = callback.data.split(":", 2)
        post_id = int(post_id_s)
        hours = None if raw == "off" else int(raw)
    except (ValueError, IndexError):
        await callback.message.answer("❌ Ошибка данных.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post or post.author_id != callback.from_user.id:
            await callback.message.answer("❌ Пост не найден.")
            return
        await repo.set_auto_delete(post_id, hours)

    await state.update_data(post_id=post_id)

    if hours is None:
        msg = (
            "✅ Для этого поста\n"
            "автоудаление <b>отключено</b>."
        )
    else:
        msg = (
            "✅ Для этого поста будет использоваться:\n\n"
            f"<b>{hours} часов</b>"
        )

    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
        await callback.message.answer(msg, parse_mode="HTML")
        await state.set_state(CreatePost.preview)
        if ctx == "queue":
            from handlers.post.preview_service import show_queue_preview
            await show_queue_preview(callback.message, state)
        else:
            from handlers.post.preview_service import show_draft_preview
            await show_draft_preview(callback.message, state)
        return

    await state.set_state(CreatePost.preview)
    await callback.message.answer(
        f"{msg}\n\n"
        "✏️ <b>Редактирование поста</b>\n\nВыберите, что хотите изменить:",
        parse_mode="HTML",
        reply_markup=edit_keyboard(),
    )
