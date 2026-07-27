import json

from aiogram import F, Router
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.formatting import formatting_keyboard
from services.button_presets import list_presets, get_preset
from states.post import CreatePost

router = Router()

HUB_TEXT = (
    "✅ Текст сохранён\n\n"
    "Что хотите сделать дальше?"
)

# После добавления кнопки — только «ещё» или назад на хаб
next_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить ещё")],
        [KeyboardButton(text="⬅ Назад")],
    ],
    resize_keyboard=True,
)


def button_source_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=preset.title,
                callback_data=f"btn_preset:{preset.key}",
            )
        ]
        for preset in list_presets()
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="✏️ Ввести вручную",
                callback_data="btn_preset:manual",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data="btn_preset:skip",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _append_button(post_id: int, text: str, url: str) -> int:
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        buttons: list[dict] = []
        if post and post.buttons:
            buttons = json.loads(post.buttons)
        buttons.append({"text": text, "url": url})
        await repo.update_buttons(post_id=post_id, buttons=buttons)
        return len(buttons)


async def _return_to_hub(message: Message, state: FSMContext, prefix: str = "") -> None:
    data = await state.get_data()
    ctx = data.get("edit_context")
    if ctx in ("queue", "draft"):
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
    text = f"{prefix}\n\n{HUB_TEXT}" if prefix else HUB_TEXT
    await message.answer(
        text,
        reply_markup=formatting_keyboard,
    )


@router.message(
    CreatePost.waiting_buttons,
    F.text == "🔗 Добавить кнопку",
)
async def add_button(message: Message, state: FSMContext):
    await message.answer(
        "🔗 <b>Добавление кнопки</b>\n\n"
        "Выберите пресет или введите вручную:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Пресеты:",
        reply_markup=button_source_keyboard(),
    )


@router.callback_query(F.data.startswith("btn_preset:"))
async def button_preset_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    key = callback.data.removeprefix("btn_preset:")

    if key == "skip":
        await _return_to_hub(callback.message, state)
        return

    if key == "manual":
        await state.set_state(CreatePost.waiting_button_text)
        await callback.message.answer(
            "✏️ Введите текст кнопки.\n\n"
            "Например:\n"
            "📺 Смотреть обзор"
        )
        return

    preset = get_preset(key)
    if not preset:
        await callback.message.answer("❌ Неизвестный пресет.")
        return

    await state.update_data(button_text=preset.title)
    await state.set_state(CreatePost.waiting_button_url)
    await callback.message.answer(
        f"✅ Пресет: <b>{preset.title}</b>\n\n"
        "🌐 Теперь отправьте ссылку.\n\n"
        "Например:\n"
        "https://youtube.com/@channel",
        parse_mode="HTML",
    )


@router.message(CreatePost.waiting_button_text)
async def button_text(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Нужен текстовый ответ.")
        return

    await state.update_data(button_text=message.text)
    await state.set_state(CreatePost.waiting_button_url)
    await message.answer(
        "🌐 Теперь отправьте ссылку.\n\n"
        "Например:\n"
        "https://youtube.com/@CyberTrip"
    )


@router.message(CreatePost.waiting_button_url)
async def button_url(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Нужна ссылка текстом.")
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    button_text_val = data.get("button_text")

    if not post_id or not button_text_val:
        await message.answer("❌ Не удалось добавить кнопку. Начните заново.")
        return

    count = await _append_button(post_id, button_text_val, message.text.strip())

    await state.set_state(CreatePost.waiting_buttons)
    await message.answer(
        f"✅ Кнопка добавлена!\n\n"
        f"Всего кнопок: {count}\n\n"
        f"Что дальше?",
        reply_markup=next_keyboard,
    )


@router.message(
    CreatePost.waiting_buttons,
    F.text == "➕ Добавить ещё",
)
async def add_more_buttons(message: Message, state: FSMContext):
    await message.answer(
        "🔗 Выберите пресет или введите вручную:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Пресеты:",
        reply_markup=button_source_keyboard(),
    )


@router.message(
    CreatePost.waiting_buttons,
    F.text.in_(["⬅ Назад", "⏭ Без кнопок", "➡️ Далее"]),
)
async def buttons_done(message: Message, state: FSMContext):
    """Возврат на главный экран управления (не в мастер расписания)."""
    await _return_to_hub(message, state)
