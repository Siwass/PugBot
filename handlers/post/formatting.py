import json

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository

from states.post import CreatePost

from keyboards.formatting import (
    formatting_keyboard,
    format_tools_keyboard,
    HUB_FORMAT,
    HUB_MEDIA,
    HUB_BUTTONS,
    HUB_POST_SETTINGS,
    HUB_PUBLISH,
    HUB_SCHEDULE,
    HUB_BACK,
    FMT_BOLD,
    FMT_ITALIC,
    FMT_UNDERLINE,
    FMT_STRIKE,
    FMT_LINK,
    FMT_TAGS,
    FMT_DONE,
    FMT_BACK,
)
from keyboards.skip import skip_keyboard
from keyboards.buttons import buttons_keyboard
from keyboards.menu import main_menu
from keyboards.preview import preview_keyboard

from services.text_formatter import (
    apply_bold,
    apply_italic,
    apply_underline,
    apply_strike,
)
from handlers.post.schedule_service import SCHEDULE_CONTEXT_NEW
from handlers.post.schedule_wizard import start_schedule_wizard
from services.publishing import answer_photo_with_text


router = Router()

HUB_TEXT = (
    "✅ Текст сохранён\n\n"
    "Что хотите сделать дальше?"
)

_FMT_ACTION_BY_TEXT = {
    FMT_BOLD: "bold",
    FMT_ITALIC: "italic",
    FMT_UNDERLINE: "underline",
    FMT_STRIKE: "strike",
    FMT_LINK: "link",
}

_FMT_PROMPT = {
    "bold": "жирной",
    "italic": "курсивом",
    "underline": "подчёркнутой",
    "strike": "зачёркнутой",
}


async def save_formatted_text(
    state: FSMContext,
    post_id: int | None,
    text: str,
) -> None:
    await state.update_data(original_text=text)

    if post_id is not None:
        async with AsyncSessionLocal() as session:
            repo = PostRepository(session)
            await repo.update_text(post_id=post_id, text=text)


async def _load_post_text(state: FSMContext) -> str:
    """Текст поста из FSM или из БД."""
    data = await state.get_data()
    text = data.get("original_text")
    if text:
        return text

    post_id = data.get("post_id")
    if not post_id:
        return ""

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if post and post.text:
            await state.update_data(original_text=post.text)
            return post.text
    return ""


async def show_hub(
    message: Message,
    state: FSMContext,
    *,
    prefix: str | None = None,
) -> None:
    """Единственная точка возврата — главный экран управления.

    Если пост из очереди (edit_context=queue) — возвращаем карточку очереди.
    """
    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
        await state.update_data(format_action=None, link_text=None, format_screen=False)
        await state.set_state(CreatePost.preview)
        if prefix:
            await message.answer(prefix)
        if ctx == "queue":
            from handlers.post.preview_service import show_queue_preview
            await show_queue_preview(message, state)
        else:
            from handlers.post.preview_service import show_draft_preview
            await show_draft_preview(message, state)
        return

    await state.set_state(CreatePost.formatting)
    await state.update_data(format_action=None, link_text=None, format_screen=False)
    text = HUB_TEXT if not prefix else f"{prefix}\n\n{HUB_TEXT}"
    await message.answer(text, reply_markup=formatting_keyboard)


async def show_format_screen(message: Message, state: FSMContext) -> None:
    """Показать текущий текст + клавиатуру инструментов форматирования."""
    await state.set_state(CreatePost.formatting)
    await state.update_data(format_action=None, link_text=None, format_screen=True)

    text = await _load_post_text(state)
    if not text:
        body = "📝 <b>Текущий текст</b>\n\n<i>(пусто)</i>"
    else:
        body = f"📝 <b>Текущий текст</b>\n\n{text}"

    await message.answer(
        body,
        parse_mode="HTML",
        reply_markup=format_tools_keyboard,
    )


# ─── Хаб (ReplyKeyboard) ───────────────────────────────


@router.message(CreatePost.formatting, F.text == HUB_FORMAT)
async def hub_format(message: Message, state: FSMContext):
    await show_format_screen(message, state)


@router.message(CreatePost.formatting, F.text == HUB_MEDIA)
async def hub_media(message: Message, state: FSMContext):
    await state.set_state(CreatePost.waiting_media)
    await message.answer(
        "📷 Отправьте фото или нажмите «Пропустить».",
        reply_markup=skip_keyboard,
    )


@router.message(CreatePost.formatting, F.text == HUB_BUTTONS)
async def hub_buttons(message: Message, state: FSMContext):
    await state.set_state(CreatePost.waiting_buttons)
    await message.answer(
        "🔗 Хотите добавить кнопку?",
        reply_markup=buttons_keyboard,
    )



@router.message(CreatePost.formatting, F.text == HUB_POST_SETTINGS)
async def hub_post_settings(message: Message, state: FSMContext):
    """Настройки конкретного поста: канал, автоудаление, кнопки."""
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await message.answer("❌ Черновик не найден.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📺 Канал",
                    callback_data="edit_channel",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏳ Автоудаление",
                    callback_data="edit_autodel",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Кнопки",
                    callback_data="edit_buttons",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="preview",
                )
            ],
        ]
    )
    await message.answer(
        "📝 <b>Настройки поста</b>\n\n"
        "Выберите, что изменить для <b>этой</b> публикации:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Разделы:", reply_markup=kb)


@router.message(CreatePost.formatting, F.text == HUB_PUBLISH)
async def hub_publish(message: Message, state: FSMContext):
    """Сразу открыть предпросмотр."""
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await message.answer("❌ Черновик не найден.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post:
        await message.answer("❌ Черновик не найден.")
        return

    inline_buttons: list[list[InlineKeyboardButton]] = []
    if post.buttons:
        for button in json.loads(post.buttons):
            inline_buttons.append(
                [InlineKeyboardButton(text=button["text"], url=button["url"])]
            )
    inline_buttons.extend(preview_keyboard.inline_keyboard)
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    await state.set_state(CreatePost.preview)

    # Скрываем reply-клавиатуру хаба на время предпросмотра
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())

    hours = post.auto_delete_hours
    if hours is None:
        adel = "⏳ Автоудаление\n\nОтключено"
    else:
        adel = f"⏳ Автоудаление\n\nДля этого поста:\n\n{hours} часов"
    await message.answer(adel)

    if post.media:
        try:
            media = json.loads(post.media)
        except (json.JSONDecodeError, TypeError):
            media = None
        if media and media.get("type") == "photo" and media.get("files"):
            try:
                await answer_photo_with_text(
                    message,
                    media["files"][0],
                    post.text or "",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception:
                await message.answer(
                    "ℹ️ Не удалось показать фото в превью.\n"
                    "Ниже — текст поста. Можно опубликовать."
                )
                await message.answer(
                    post.text or "Без текста",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return

    await message.answer(
        post.text or "Без текста",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.message(CreatePost.formatting, F.text == HUB_SCHEDULE)
async def hub_schedule(message: Message, state: FSMContext):
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


@router.message(CreatePost.formatting, F.text == HUB_BACK)
async def hub_back(message: Message, state: FSMContext):
    data = await state.get_data()
    # На экране форматирования «Назад» = выход к хабу, не отмена поста
    if data.get("format_screen"):
        await show_hub(message, state)
        return
    await state.clear()
    await message.answer(
        "↩️ Создание поста отменено.",
        reply_markup=main_menu,
    )


# ─── Инструменты форматирования (ReplyKeyboard) ────────


@router.message(
    CreatePost.formatting,
    F.text.in_(list(_FMT_ACTION_BY_TEXT.keys())),
)
async def format_tool_chosen(message: Message, state: FSMContext):
    """Выбор типа оформления на экране форматирования."""
    if message.text is None:
        return

    action = _FMT_ACTION_BY_TEXT.get(message.text)
    if not action:
        return

    if action == "link":
        await state.set_state(CreatePost.waiting_link_text)
        await message.answer(
            "🔗 Отправьте слово или фразу из текста выше,\n"
            "которую нужно сделать ссылкой."
        )
        return

    await state.update_data(format_action=action)
    await state.set_state(CreatePost.waiting_format_text)

    how = _FMT_PROMPT.get(action, "оформленной")
    await message.answer(
        f"Отправьте слово или фразу\n"
        f"из текста выше,\n"
        f"которую необходимо сделать {how}."
    )


@router.message(CreatePost.formatting, F.text == FMT_TAGS)
async def format_tags(message: Message, state: FSMContext):
    """Открыть выбор тегов (прежняя логика tags_open)."""
    await state.update_data(pending_tags=[], tags_category=None, format_screen=True)
    from handlers.post.tags import categories_keyboard

    await message.answer(
        "🏷 <b>Теги</b>\n\nВыберите категорию:",
        parse_mode="HTML",
        reply_markup=categories_keyboard(),
    )


@router.message(
    CreatePost.formatting,
    F.text.in_({FMT_DONE, FMT_BACK}),
)
async def format_done_or_back(message: Message, state: FSMContext):
    """Готово / Назад → экран управления публикацией."""
    await show_hub(message, state)


@router.message(CreatePost.waiting_format_text)
async def apply_formatting(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Не удалось получить текст.")
        return

    # Если пользователь нажал кнопку клавиатуры вместо фразы
    if message.text == FMT_TAGS:
        await state.set_state(CreatePost.formatting)
        await format_tags(message, state)
        return
    if message.text in _FMT_ACTION_BY_TEXT or message.text in {FMT_DONE, FMT_BACK}:
        if message.text in {FMT_DONE, FMT_BACK}:
            await show_hub(message, state)
            return
        # Переключение на другое оформление
        await state.set_state(CreatePost.formatting)
        await format_tool_chosen(message, state)
        return

    data = await state.get_data()
    action = data.get("format_action")
    text = await _load_post_text(state)

    if not text:
        await message.answer(
            "❌ Текст поста не найден.\n"
            "Вернитесь и задайте текст заново."
        )
        await show_hub(message, state)
        return

    fragment = message.text
    if fragment not in text:
        await message.answer(
            "❌ Фраза не найдена в тексте.\n\n"
            "Скопируйте фрагмент точно из текста выше и отправьте снова."
        )
        return

    if action == "bold":
        text = apply_bold(text, fragment)
    elif action == "italic":
        text = apply_italic(text, fragment)
    elif action == "underline":
        text = apply_underline(text, fragment)
    elif action == "strike":
        text = apply_strike(text, fragment)

    await save_formatted_text(state, data.get("post_id"), text)

    # Снова показываем обновлённый текст и меню форматирования
    await show_format_screen(message, state)


@router.message(CreatePost.waiting_link_text)
async def get_link_text(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Не удалось получить текст ссылки.")
        return

    if message.text in {FMT_DONE, FMT_BACK}:
        await show_hub(message, state)
        return

    if message.text in _FMT_ACTION_BY_TEXT:
        await state.set_state(CreatePost.formatting)
        await format_tool_chosen(message, state)
        return

    await state.update_data(link_text=message.text)
    await state.set_state(CreatePost.waiting_link_url)
    await message.answer("🔗 Теперь отправьте URL:")


@router.message(CreatePost.waiting_link_url)
async def get_link_url(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Не удалось получить URL.")
        return

    if message.text in {FMT_DONE, FMT_BACK}:
        await show_hub(message, state)
        return

    data = await state.get_data()
    link_text = data.get("link_text")
    text = await _load_post_text(state)

    if not text or not link_text:
        await message.answer("❌ Не удалось создать ссылку.")
        await show_format_screen(message, state)
        return

    if link_text not in text:
        await message.answer(
            "❌ Фраза не найдена в тексте.\n"
            "Начните добавление ссылки заново."
        )
        await show_format_screen(message, state)
        return

    text = text.replace(
        link_text,
        f'<a href="{message.text}">{link_text}</a>',
        1,
    )

    await save_formatted_text(state, data.get("post_id"), text)
    await show_format_screen(message, state)
