from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.formatting import formatting_keyboard
from services.tags_catalog import (
    get_category,
    list_categories,
    merge_tags_into_text,
    normalize_tag,
)
from states.post import CreatePost

router = Router()


def categories_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in list_categories():
        rows.append(
            [
                InlineKeyboardButton(
                    text=cat.title,
                    callback_data=f"tags_cat:{cat.key}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⏭ Без тегов",
                callback_data="tags_skip",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def more_tags_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data="tags_more_yes",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➡️ Нет, продолжить",
                    callback_data="tags_more_no",
                )
            ],
        ]
    )


def extra_tags_keyboard(category_key: str, selected: list[str]) -> InlineKeyboardMarkup:
    cat = get_category(category_key)
    rows: list[list[InlineKeyboardButton]] = []
    selected_set = {normalize_tag(t) for t in selected}

    if cat:
        for label, raw in cat.extra_tags:
            tag = normalize_tag(raw)
            mark = "✅ " if tag in selected_set else ""
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{mark}{label}",
                        callback_data=f"tags_extra:{category_key}:{raw}",
                    )
                ]
            )

    rows.append(
        [
            InlineKeyboardButton(
                text="✍️ Свой тег",
                callback_data="tags_custom",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="✅ Готово",
                callback_data="tags_done",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _current_text(state: FSMContext) -> str:
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
        return (post.text if post else "") or ""


async def _save_text(state: FSMContext, text: str) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
    await state.update_data(original_text=text)
    if post_id:
        async with AsyncSessionLocal() as session:
            repo = PostRepository(session)
            await repo.update_text(post_id, text)


@router.callback_query(F.data == "tags_open")
async def tags_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    await state.set_state(CreatePost.formatting)
    await state.update_data(pending_tags=[], tags_category=None)

    await callback.message.answer(
        "🏷 <b>Теги</b>\n\nВыберите категорию:",
        parse_mode="HTML",
        reply_markup=categories_keyboard(),
    )


@router.callback_query(F.data == "tags_skip")
async def tags_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    await state.update_data(pending_tags=[], tags_category=None)
    data = await state.get_data()
    if data.get("format_screen"):
        from handlers.post.formatting import show_format_screen
        await show_format_screen(callback.message, state)
        return
    await state.set_state(CreatePost.formatting)
    await callback.message.answer(
        "🏷 Без тегов.\n\nЧто хотите сделать дальше?",
        reply_markup=formatting_keyboard,
    )


@router.callback_query(F.data.startswith("tags_cat:"))
async def tags_category_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    key = callback.data.removeprefix("tags_cat:")
    cat = get_category(key)
    if not cat:
        await callback.message.answer("❌ Категория не найдена.")
        return

    pending = list(cat.base_tags)
    await state.update_data(
        tags_category=key,
        pending_tags=pending,
    )

    await callback.message.answer(
        f"✅ Категория: <b>{cat.title}</b>\n\n"
        f"Базовые теги:\n{' '.join(pending)}\n\n"
        "➕ Добавить ещё теги?",
        parse_mode="HTML",
        reply_markup=more_tags_prompt_keyboard(),
    )


@router.callback_query(F.data == "tags_more_yes")
async def tags_more_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    key = data.get("tags_category")
    pending = list(data.get("pending_tags") or [])
    if not key:
        await callback.message.answer("❌ Сначала выберите категорию.")
        return

    await callback.message.answer(
        "Выберите дополнительные теги (можно несколько):\n\n"
        f"Уже выбрано: {' '.join(pending)}",
        reply_markup=extra_tags_keyboard(key, pending),
    )


@router.callback_query(F.data == "tags_more_no")
async def tags_more_no(callback: CallbackQuery, state: FSMContext):
    """Сразу применить базовые теги и вернуться к оформлению."""
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await _apply_pending_tags(callback.message, state)


@router.callback_query(F.data.startswith("tags_extra:"))
async def tags_extra_toggle(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    # tags_extra:{category}:{raw}
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return
    _, key, raw = parts
    tag = normalize_tag(raw)
    if not tag:
        return

    data = await state.get_data()
    pending = list(data.get("pending_tags") or [])
    pending_norm = [normalize_tag(t) for t in pending]

    if tag in pending_norm:
        pending = [t for t in pending if normalize_tag(t) != tag]
    else:
        pending.append(tag)

    await state.update_data(pending_tags=pending, tags_category=key)

    try:
        await callback.message.edit_text(
            "Выберите дополнительные теги (можно несколько):\n\n"
            f"Уже выбрано: {' '.join(pending)}",
            reply_markup=extra_tags_keyboard(key, pending),
        )
    except Exception:
        await callback.message.answer(
            f"Уже выбрано: {' '.join(pending)}",
            reply_markup=extra_tags_keyboard(key, pending),
        )


@router.callback_query(F.data == "tags_custom")
async def tags_custom_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    await state.set_state(CreatePost.waiting_custom_tag)
    await callback.message.answer(
        "✍️ Введите свой тег.\n\n"
        "Можно так: <code>iphone17</code> или <code>#iphone17</code>",
        parse_mode="HTML",
    )


@router.message(CreatePost.waiting_custom_tag)
async def tags_custom_save(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Нужен текст тега.")
        return

    tag = normalize_tag(message.text)
    if not tag or tag == "#":
        await message.answer("❌ Пустой тег. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    pending = list(data.get("pending_tags") or [])
    key = data.get("tags_category") or "other"

    if tag not in {normalize_tag(t) for t in pending}:
        pending.append(tag)

    await state.update_data(pending_tags=pending)
    await state.set_state(CreatePost.formatting)

    await message.answer(
        f"✅ Добавлено: {tag}\n\n"
        f"Уже выбрано: {' '.join(pending)}",
        reply_markup=extra_tags_keyboard(key, pending),
    )


@router.callback_query(F.data == "tags_done")
async def tags_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await _apply_pending_tags(callback.message, state)


async def _apply_pending_tags(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pending = list(data.get("pending_tags") or [])

    text = await _current_text(state)
    new_text = merge_tags_into_text(text, pending)
    await _save_text(state, new_text)

    await state.update_data(pending_tags=[], tags_category=None)

    if pending:
        await message.answer(
            f"✅ Теги добавлены:\n{' '.join(normalize_tag(t) for t in pending)}"
        )
    else:
        await message.answer("🏷 Теги не добавлены.")

    data = await state.get_data()
    if data.get("format_screen"):
        from handlers.post.formatting import show_format_screen
        await show_format_screen(message, state)
        return

    await state.set_state(CreatePost.formatting)
    await message.answer(
        "Что хотите сделать дальше?",
        reply_markup=formatting_keyboard,
    )
