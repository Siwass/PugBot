import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from database.template_repository import TemplateRepository
from database.user_settings_repository import UserSettingsRepository
from states.post import CreatePost
from keyboards.menu import main_menu

router = Router()


def templates_list_keyboard(templates, *, for_pick: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for template in templates:
        mark = "" if template.is_system else "👤 "
        prefix = "tpl_use" if for_pick else "tpl_view"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{template.name}",
                    callback_data=f"{prefix}:{template.id}",
                )
            ]
        )
    if not for_pick:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➕ Создать свой шаблон",
                    callback_data="tpl_create",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="⬅️ Закрыть", callback_data="tpl_close")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_view_keyboard(template) -> InlineKeyboardMarkup:
    rows = []
    if not template.is_system:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Удалить шаблон",
                    callback_data=f"tpl_delete:{template.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📋 Использовать",
                callback_data=f"tpl_use:{template.id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="tpl_list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "📋 Шаблоны")
async def templates_menu(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    await state.clear()

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        templates = await repo.ensure_defaults(message.from_user.id)

    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "📋 <b>Шаблоны</b>\n\n"
        "👤 — ваши шаблоны\n"
        "Остальные — системные.\n\n"
        "Выберите шаблон или создайте свой.",
        parse_mode="HTML",
        reply_markup=templates_list_keyboard(templates, for_pick=False),
    )


@router.callback_query(F.data == "tpl_list")
async def templates_list_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    await state.clear()

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        templates = await repo.ensure_defaults(callback.from_user.id)

    await callback.message.answer(
        "📋 <b>Шаблоны</b>",
        parse_mode="HTML",
        reply_markup=templates_list_keyboard(templates, for_pick=False),
    )


@router.callback_query(F.data == "new_post_from_template")
async def pick_template_for_new_post(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        templates = await repo.ensure_defaults(callback.from_user.id)

    await callback.message.answer(
        "📋 <b>Выберите шаблон</b>\n\n"
        "После выбора сможете изменить текст.",
        parse_mode="HTML",
        reply_markup=templates_list_keyboard(templates, for_pick=True),
    )


@router.callback_query(F.data.startswith("tpl_use:"))
async def use_template(callback: CallbackQuery, state: FSMContext):
    """Работает для ЛЮБОГО шаблона (системного и своего)."""
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    if callback.data is None:
        return

    try:
        template_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer("❌ Некорректный шаблон.")
        return

    async with AsyncSessionLocal() as session:
        tpl_repo = TemplateRepository(session)
        post_repo = PostRepository(session)
        settings_repo = UserSettingsRepository(session)

        template = await tpl_repo.get_by_id(template_id)
        if not template or template.user_id != callback.from_user.id:
            await callback.message.answer("❌ Шаблон не найден.")
            return

        post = await post_repo.create(author_id=callback.from_user.id)
        await post_repo.update_text(post.id, template.text)
        if template.buttons:
            try:
                buttons = json.loads(template.buttons)
                if isinstance(buttons, list):
                    await post_repo.update_buttons(post.id, buttons)
            except json.JSONDecodeError:
                pass

        settings = await settings_repo.get(callback.from_user.id)
        if settings and settings.default_channel_id:
            await post_repo.update_channel(post.id, settings.default_channel_id)
        if settings and settings.default_auto_delete_hours:
            await post_repo.set_auto_delete(
                post.id, settings.default_auto_delete_hours
            )

        post_id = post.id
        name = template.name
        text = template.text

    await state.clear()
    await state.update_data(
        post_id=post_id,
        original_text=text,
        from_template=True,
    )
    await state.set_state(CreatePost.preview)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Изменить текст",
                    callback_data="tpl_edit_text",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➡️ Оставить как есть",
                    callback_data="tpl_keep_text",
                )
            ],
        ]
    )

    await callback.message.answer(
        f"✅ Шаблон «{name}» применён.\n"
        f"Черновик №{post_id}\n\n"
        f"Текущий текст:\n{text}\n\n"
        "Хотите изменить текст или оставить шаблон?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "tpl_edit_text")
async def template_edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    current = data.get("original_text") or ""
    await state.update_data(from_template=True)
    await state.set_state(CreatePost.editing_text)

    hint = f"\n\nСейчас:\n{current}" if current else ""
    await callback.message.answer(
        "✍️ Отправьте новый текст поста." + hint
    )


@router.callback_query(F.data == "tpl_keep_text")
async def template_keep_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.message.answer("❌ Пост не найден.")
        return

    await state.update_data(from_template=None)
    await state.set_state(CreatePost.formatting)

    from keyboards.formatting import formatting_keyboard

    await callback.message.answer(
        "✅ Текст шаблона оставлен.\n\n"
        "🎨 Хотите оформить текст?\n\n"
        "Выберите действие:",
        reply_markup=formatting_keyboard,
    )


@router.callback_query(F.data.startswith("tpl_view:"))
async def view_template(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    if callback.data is None:
        return

    try:
        template_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        template = await repo.get_by_id(template_id)

    if not template or template.user_id != callback.from_user.id:
        await callback.message.answer("❌ Шаблон не найден.")
        return

    kind = "системный" if template.is_system else "ваш"
    await callback.message.answer(
        f"📋 <b>{template.name}</b> <i>({kind})</i>\n\n"
        f"{template.text}",
        parse_mode="HTML",
        reply_markup=template_view_keyboard(template),
    )


@router.callback_query(F.data == "tpl_create")
async def template_create_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    await state.set_state(CreatePost.waiting_template_name)
    await callback.message.answer(
        "➕ <b>Новый шаблон</b>\n\n"
        "Введите название шаблона.\n"
        "Например: <code>Обзор товара</code>",
        parse_mode="HTML",
    )


@router.message(CreatePost.waiting_template_name)
async def template_name_received(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("❌ Нужно название текстом.")
        return

    name = message.text.strip()
    if len(name) > 100:
        await message.answer("❌ Слишком длинное название (макс. 100 символов).")
        return

    await state.update_data(template_name=name)
    await state.set_state(CreatePost.waiting_template_text)
    await message.answer(
        f"Название: <b>{name}</b>\n\n"
        "Теперь отправьте текст шаблона.",
        parse_mode="HTML",
    )


@router.message(CreatePost.waiting_template_text)
async def template_text_received(message: Message, state: FSMContext):
    if message.from_user is None:
        return
    if not message.text or not message.text.strip():
        await message.answer("❌ Нужен текст шаблона.")
        return

    data = await state.get_data()
    name = data.get("template_name")
    if not name:
        await message.answer("❌ Сначала укажите название. Откройте «📋 Шаблоны» снова.")
        await state.clear()
        return

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        template = await repo.create(
            user_id=message.from_user.id,
            name=name,
            text=message.text,
            buttons=None,
            is_system=False,
        )
        templates = await repo.list_for_user(message.from_user.id)

    await state.clear()
    await message.answer(
        f"✅ Шаблон «{template.name}» создан (№{template.id}).\n\n"
        "Он появится в списке с меткой 👤.",
        reply_markup=templates_list_keyboard(templates, for_pick=False),
    )


@router.callback_query(F.data.startswith("tpl_delete:"))
async def template_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return

    try:
        template_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        repo = TemplateRepository(session)
        ok = await repo.delete(template_id, callback.from_user.id)
        templates = await repo.ensure_defaults(callback.from_user.id)

    if not ok:
        await callback.message.answer(
            "❌ Не удалось удалить.\n"
            "Системные шаблоны удалять нельзя."
        )
        return

    await callback.message.answer(
        "🗑 Шаблон удалён.",
        reply_markup=templates_list_keyboard(templates, for_pick=False),
    )


@router.callback_query(F.data == "tpl_close")
async def templates_close(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "📋 Шаблоны закрыты.",
            reply_markup=main_menu,
        )
