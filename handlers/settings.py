import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from database.bot_admin_repository import BotAdminRepository
from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal
from database.user_settings_repository import UserSettingsRepository
from config import OWNER_ID
from keyboards.menu import main_menu
from states.admin import AdminStates

router = Router()
logger = logging.getLogger(__name__)

SETTINGS_TEXT = (
    "⚙️ <b>Настройки</b>\n\n"
    "Выберите раздел:"
)

EMPTY_CHANNELS_TEXT = (
    "📺 <b>Ваши каналы</b>\n\n"
    "У вас пока нет подключённых каналов."
)

ADD_CHANNEL_TEXT = (
    "➕ <b>Добавить канал</b>\n\n"
    "1. Откройте нужный Telegram-канал\n"
    "2. Добавьте этого бота <b>администратором</b>\n"
    "3. Выдайте право <b>«Публикация сообщений»</b>\n\n"
    "После этого канал появится здесь автоматически.\n\n"
    "<i>Бот пришлёт подтверждение, когда канал будет подключён.</i>"
)


def _nav_rows(*extra: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    rows = list(extra) if extra else []
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="settings_to_menu"),
        ]
    )
    return rows


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 Каналы", callback_data="settings_channels")],
            [InlineKeyboardButton(text="⭐ Основной канал", callback_data="settings_default_channel")],
            [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="settings_timezone")],
            [InlineKeyboardButton(text="⏳ Автоудаление", callback_data="settings_auto_delete")],
            [InlineKeyboardButton(text="👤 Администраторы", callback_data="settings_admins")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="settings_to_menu")],
        ]
    )


def empty_channels_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=_nav_rows(
            [InlineKeyboardButton(text="➕ Добавить канал", callback_data="channels_add")],
        )
    )


def channel_list_keyboard(channels) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📺 {ch.title or 'Канал'}",
                    callback_data=f"channel_info:{ch.telegram_chat_id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="channels_add")]
    )
    buttons.extend(_nav_rows())
    # _nav_rows already has back+home; but we used settings_back - ok
    # Fix: _nav_rows returns list with one row - need to append properly
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def default_channel_keyboard(channels, current_id: int | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        mark = "✅ " if current_id == ch.id else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{ch.title or 'Канал'}",
                    callback_data=f"set_default_channel:{ch.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Сбросить",
                callback_data="set_default_channel:0",
            )
        ]
    )
    rows.extend(_nav_rows())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_channel_info(ch) -> str:
    username = f"@{ch.username}" if ch.username else "—"
    return (
        f"📺 <b>{ch.title or 'Канал'}</b>\n\n"
        f"ID: <code>{ch.telegram_chat_id}</code>\n"
        f"Username: {username}"
    )


# ─── Открытие ──────────────────────────────────────────


@router.message(F.text == "⚙️ Настройки")
async def open_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        SETTINGS_TEXT,
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


@router.callback_query(F.data == "settings_back")
async def back_to_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SETTINGS_TEXT,
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )


@router.callback_query(F.data == "settings_to_menu")
async def settings_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
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


# ─── Каналы ────────────────────────────────────────────


@router.callback_query(F.data == "settings_channels")
async def show_channels_list(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_channels_for_user(callback.from_user.id)

    if not channels:
        await callback.message.edit_text(
            EMPTY_CHANNELS_TEXT,
            parse_mode="HTML",
            reply_markup=empty_channels_keyboard(),
        )
        return

    await callback.message.edit_text(
        "📺 <b>Ваши каналы</b>\n\nВыберите канал:",
        parse_mode="HTML",
        reply_markup=channel_list_keyboard(channels),
    )


@router.callback_query(F.data == "channels_add")
async def channels_add_help(callback: CallbackQuery) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.edit_text(
        ADD_CHANNEL_TEXT,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=_nav_rows()),
    )


@router.callback_query(F.data.startswith("channel_info:"))
async def show_single_channel(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return

    try:
        chat_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        repo = ChannelRepository(session)
        user_channels = await repo.get_channels_for_user(callback.from_user.id)
        channel = next(
            (ch for ch in user_channels if ch.telegram_chat_id == chat_id),
            None,
        )

    if not channel:
        await callback.message.edit_text(
            "❌ Канал не найден",
            reply_markup=empty_channels_keyboard(),
        )
        return

    await callback.message.edit_text(
        format_channel_info(channel),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад к списку",
                        callback_data="settings_channels",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="settings_to_menu",
                    )
                ],
            ]
        ),
    )


# ─── Основной канал ────────────────────────────────────


@router.callback_query(F.data == "settings_default_channel")
async def settings_default_channel(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_channels_for_user(callback.from_user.id)
        settings = await UserSettingsRepository(session).get(callback.from_user.id)
        current_id = settings.default_channel_id if settings else None

    if not channels:
        await callback.message.edit_text(
            EMPTY_CHANNELS_TEXT,
            parse_mode="HTML",
            reply_markup=empty_channels_keyboard(),
        )
        return

    await callback.message.edit_text(
        "⭐ <b>Основной канал</b>\n\nВыберите канал по умолчанию:",
        parse_mode="HTML",
        reply_markup=default_channel_keyboard(channels, current_id),
    )


@router.callback_query(F.data.startswith("set_default_channel:"))
async def set_default_channel(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return

    try:
        raw = callback.data.split(":")[1]
        channel_id = int(raw)
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        settings_repo = UserSettingsRepository(session)
        if channel_id == 0:
            await settings_repo.set_default_channel(callback.from_user.id, None)
            text = "✅ Основной канал сброшен."
        else:
            await settings_repo.set_default_channel(callback.from_user.id, channel_id)
            text = "✅ Основной канал сохранён."

    await callback.message.edit_text(
        text,
        reply_markup=settings_keyboard(),
    )


# ─── Часовой пояс ──────────────────────────────────────


def timezone_keyboard(current: str | None) -> InlineKeyboardMarkup:
    from utils.timezones import COMMON_TIMEZONES

    rows: list[list[InlineKeyboardButton]] = []
    for code, label in COMMON_TIMEZONES:
        mark = "✅ " if current == code else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"set_tz:{code}",
                )
            ]
        )
    rows.extend(_nav_rows())
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "settings_timezone")
async def settings_timezone(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    async with AsyncSessionLocal() as session:
        settings = await UserSettingsRepository(session).get_or_create(
            callback.from_user.id
        )
        current = settings.timezone
    from utils.timezones import format_tz_label

    await callback.message.edit_text(
        "🌍 <b>Часовой пояс</b>\n\n"
        f"Сейчас: <b>{format_tz_label(current)}</b>\n\n"
        "Выберите пояс для планирования постов.",
        parse_mode="HTML",
        reply_markup=timezone_keyboard(current),
    )


@router.callback_query(F.data.startswith("set_tz:"))
async def set_timezone(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return
    tz = callback.data.removeprefix("set_tz:")
    async with AsyncSessionLocal() as session:
        await UserSettingsRepository(session).set_timezone(
            callback.from_user.id, tz
        )
    from utils.timezones import format_tz_label

    await callback.message.edit_text(
        f"✅ Часовой пояс: <b>{format_tz_label(tz)}</b>",
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


# ─── Автоудаление ──────────────────────────────────────


AUTO_DELETE_OPTIONS = (24, 48, 72, 96)


def _autodel_label(hours: int | None) -> str:
    if hours is None:
        return "выкл"
    return f"{hours} ч"


def auto_delete_keyboard(current: int | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for hours in AUTO_DELETE_OPTIONS:
        mark = "✅ " if current == hours else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{hours} ч",
                    callback_data=f"ask_autodel:{hours}",
                )
            ]
        )
    off_mark = "✅ " if current is None else ""
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{off_mark}Выкл",
                callback_data="ask_autodel:off",
            )
        ]
    )
    rows.extend(_nav_rows())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _autodel_confirm_keyboard(raw: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, изменить",
                    callback_data=f"confirm_autodel:{raw}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="settings_auto_delete",
                )
            ],
        ]
    )


@router.callback_query(F.data == "settings_auto_delete")
async def settings_auto_delete(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    async with AsyncSessionLocal() as session:
        settings = await UserSettingsRepository(session).get_or_create(
            callback.from_user.id
        )
        current = settings.default_auto_delete_hours
    cur_label = _autodel_label(current)
    await callback.message.edit_text(
        "⏳ <b>Автоудаление по умолчанию</b>\n\n"
        f"Сейчас: <b>{cur_label}</b>\n\n"
        "Эта настройка применяется ко <b>всем новым публикациям</b>,\n"
        "если для конкретного поста не выбрано другое значение.\n\n"
        "⚠️ Изменяйте её внимательно.",
        parse_mode="HTML",
        reply_markup=auto_delete_keyboard(current),
    )


@router.callback_query(F.data.startswith("ask_autodel:"))
async def ask_auto_delete_default(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    raw = callback.data.removeprefix("ask_autodel:")
    hours = None if raw == "off" else int(raw)
    value_label = "выключено" if hours is None else f"{hours} часов"
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение</b>\n\n"
        "Вы собираетесь изменить\n"
        "автоудаление по умолчанию\n"
        "для всех новых публикаций.\n\n"
        f"Новое значение:\n\n"
        f"<b>{value_label}</b>\n\n"
        "Продолжить?",
        parse_mode="HTML",
        reply_markup=_autodel_confirm_keyboard(raw),
    )


@router.callback_query(F.data.startswith("confirm_autodel:"))
async def confirm_auto_delete_default(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return
    raw = callback.data.removeprefix("confirm_autodel:")
    hours = None if raw == "off" else int(raw)
    async with AsyncSessionLocal() as session:
        await UserSettingsRepository(session).set_default_auto_delete(
            callback.from_user.id, hours
        )
    if hours is None:
        body = (
            "✅ <b>Настройка сохранена.</b>\n\n"
            "Автоудаление по умолчанию <b>выключено</b>.\n\n"
            "Новые публикации не будут удаляться автоматически,\n"
            "если для поста не задано другое значение."
        )
    else:
        body = (
            "✅ <b>Настройка сохранена.</b>\n\n"
            "Теперь все новые публикации\n"
            "по умолчанию будут удаляться\n"
            f"через <b>{hours} часов</b>.\n\n"
            "Для отдельных постов можно\n"
            "выбрать другое значение\n"
            "в настройках поста."
        )
    await callback.message.edit_text(
        body,
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


# ─── Администраторы PugBot ─────────────────────────────


def _admin_label(admin) -> str:
    """Человекочитаемая подпись для списка и кнопок."""
    if admin.display_name and admin.username:
        body = f"{admin.display_name}\n@{admin.username}"
    elif admin.display_name:
        body = admin.display_name
    elif admin.username:
        body = f"@{admin.username}"
    else:
        body = f"ID: {admin.user_id}"

    icon = "👑" if admin.is_owner else "👤"
    return f"{icon} {body}"


def _admin_label_one_line(admin) -> str:
    """Однострочная подпись (кнопки удаления)."""
    if admin.display_name and admin.username:
        name = f"{admin.display_name} (@{admin.username})"
    elif admin.display_name:
        name = admin.display_name
    elif admin.username:
        name = f"@{admin.username}"
    else:
        name = f"ID: {admin.user_id}"
    icon = "👑" if admin.is_owner else "👤"
    return f"{icon} {name}"


def _admins_list_text(admins: list) -> str:
    total = len(admins)
    if admins:
        lines = "\n\n".join(_admin_label(a) for a in admins)
    else:
        lines = "Список пуст."
    return (
        f"👥 <b>Администраторы</b>\n\n"
        f"Всего: {total}\n\n"
        f"{lines}\n\n"
        f"────────────\n"
        f"👑 Владелец проекта не может быть удалён."
    )


def _admins_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
            [InlineKeyboardButton(text="➖ Удалить", callback_data="admin_remove_list")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="settings_to_menu"),
            ],
        ]
    )


async def _enrich_admin_profile(bot, admin) -> None:
    """Подтянуть имя/username из Telegram, если в БД только ID."""
    if admin.display_name and admin.username:
        return
    try:
        chat = await bot.get_chat(admin.user_id)
    except Exception:
        return

    display_name = None
    if getattr(chat, "full_name", None):
        display_name = chat.full_name
    elif getattr(chat, "first_name", None):
        parts = [chat.first_name]
        if getattr(chat, "last_name", None):
            parts.append(chat.last_name)
        display_name = " ".join(parts)

    username = getattr(chat, "username", None) or None
    if not display_name and not username:
        return

    changed = False
    if display_name and not admin.display_name:
        admin.display_name = display_name
        changed = True
    elif display_name and admin.display_name == str(admin.user_id):
        admin.display_name = display_name
        changed = True
    if username and not admin.username:
        admin.username = username
        changed = True

    if not changed:
        return

    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        existing = await repo.get(admin.user_id)
        if existing is None:
            return
        if display_name and (
            not existing.display_name or existing.display_name == str(existing.user_id)
        ):
            existing.display_name = display_name
        if username and not existing.username:
            existing.username = username
        await session.commit()
        await session.refresh(existing)
        admin.display_name = existing.display_name
        admin.username = existing.username


async def _load_admins_enriched(bot) -> list:
    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        admins = await repo.list_all()
    for admin in admins:
        await _enrich_admin_profile(bot, admin)
    return admins


async def _show_admins_list(target: Message) -> None:
    admins = await _load_admins_enriched(target.bot)
    await target.edit_text(
        _admins_list_text(admins),
        parse_mode="HTML",
        reply_markup=_admins_list_keyboard(),
    )


@router.callback_query(F.data == "settings_admins")
async def settings_admins(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if not isinstance(callback.message, Message):
        return
    await _show_admins_list(callback.message)


@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await state.set_state(AdminStates.waiting_new_admin)
    await callback.message.edit_text(
        "➕ <b>Добавить администратора</b>\n\n"
        "Отправьте:\n\n"
        "• <code>@username</code>\n\n"
        "или\n\n"
        "• Telegram ID\n\n"
        "или\n\n"
        "• просто перешлите сообщение пользователя.\n\n"
        "────────────\n\n"
        "⚠️ <b>Важно</b>\n\n"
        "Новый администратор получит доступ\n"
        "к управлению <b>PugBot</b>.\n\n"
        "Укажите верный @username или ID.\n"
        "Пользователь должен хотя бы раз\n"
        "открыть диалог с ботом.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="settings_admins",
                    )
                ]
            ]
        ),
    )


@router.message(AdminStates.waiting_new_admin)
async def admin_add_receive(message: Message, state: FSMContext) -> None:
    user_id: int | None = None
    display_name: str | None = None
    username: str | None = None

    # Пересланное сообщение
    if message.forward_from is not None:
        src = message.forward_from
        user_id = src.id
        display_name = src.full_name
        username = src.username
    elif message.forward_sender_name:
        await message.answer(
            "❌ Не удалось определить пользователя "
            "(скрытый аккаунт при пересылке).\n"
            "Отправьте @username или Telegram ID."
        )
        return
    elif message.text:
        raw = message.text.strip()
        if raw.startswith("@"):
            try:
                chat = await message.bot.get_chat(raw)
                user_id = chat.id
                display_name = chat.full_name if hasattr(chat, "full_name") else (
                    chat.first_name or raw
                )
                username = chat.username or raw.lstrip("@")
            except Exception as exc:
                logger.warning(
                    "Не удалось найти пользователя по username: %s",
                    exc,
                )
                await message.answer(
                    "❌ <b>Пользователь не найден</b>\n\n"
                    "Проверьте @username или отправьте\n"
                    "Telegram ID / перешлите сообщение.",
                    parse_mode="HTML",
                )
                return
        elif raw.lstrip("-").isdigit():
            user_id = int(raw)
            display_name = None
            try:
                chat = await message.bot.get_chat(user_id)
                if getattr(chat, "full_name", None):
                    display_name = chat.full_name
                elif getattr(chat, "first_name", None):
                    parts = [chat.first_name]
                    if getattr(chat, "last_name", None):
                        parts.append(chat.last_name)
                    display_name = " ".join(parts)
                username = getattr(chat, "username", None) or None
            except Exception:
                display_name = None
        else:
            await message.answer(
                "❌ Не распознано. Отправьте @username, ID или перешлите сообщение."
            )
            return
    else:
        await message.answer("❌ Отправьте текст или перешлите сообщение.")
        return

    if user_id is None:
        await message.answer("❌ Не удалось определить ID.")
        return

    # Владелец уже с полным доступом
    if OWNER_ID is not None and user_id == OWNER_ID:
        await state.clear()
        await message.answer(
            "👑 <b>Владелец проекта</b>\n\n"
            "уже обладает\n"
            "полным доступом.\n\n"
            "Дополнительное назначение\n"
            "не требуется.",
            parse_mode="HTML",
        )
        admins = await _load_admins_enriched(message.bot)
        await message.answer(
            _admins_list_text(admins),
            parse_mode="HTML",
            reply_markup=_admins_list_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        existing = await repo.get(user_id)
        if existing is not None:
            await state.clear()
            await message.answer(
                "ℹ️ Этот пользователь\n\n"
                "уже является\n"
                "администратором PugBot.",
                parse_mode="HTML",
            )
            admins = await _load_admins_enriched(message.bot)
            await message.answer(
                _admins_list_text(admins),
                parse_mode="HTML",
                reply_markup=_admins_list_keyboard(),
            )
            return

        added = await repo.add(
            user_id,
            display_name=display_name,
            username=username,
        )

    await state.clear()

    if added is None:
        await message.answer(
            "ℹ️ Этот пользователь\n\n"
            "уже является\n"
            "администратором PugBot.",
            parse_mode="HTML",
        )
    else:
        if display_name and username:
            who = f"👤 {display_name}\n(@{username})"
        elif display_name:
            who = f"👤 {display_name}"
        elif username:
            who = f"👤 @{username}"
        else:
            who = f"👤 ID: {user_id}"
        await message.answer(
            "✅ <b>Администратор добавлен</b>\n\n"
            f"{who}\n\n"
            "теперь имеет доступ\n"
            "к управлению PugBot.",
            parse_mode="HTML",
        )

    admins = await _load_admins_enriched(message.bot)
    await message.answer(
        _admins_list_text(admins),
        parse_mode="HTML",
        reply_markup=_admins_list_keyboard(),
    )


@router.callback_query(F.data == "admin_remove_list")
async def admin_remove_list(callback: CallbackQuery) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = BotAdminRepository(session)
        admins = await repo.list_all()

    removable = [a for a in admins if not a.is_owner]
    if not removable:
        await callback.message.edit_text(
            "ℹ️ Некого удалять.\nВладельца удалить нельзя.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ Назад",
                            callback_data="settings_admins",
                        )
                    ]
                ]
            ),
        )
        return

    rows = [
        [
            InlineKeyboardButton(
                text=_admin_label_one_line(a).replace("👑 ", "").replace("👤 ", ""),
                callback_data=f"admin_del_ask:{a.user_id}",
            )
        ]
        for a in removable
    ]
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_admins")]
    )
    await callback.message.edit_text(
        "➖ <b>Удалить администратора</b>\n\nВыберите:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("admin_del_ask:"))
async def admin_del_ask(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    try:
        uid = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        admin = await BotAdminRepository(session).get(uid)
    if not admin or admin.is_owner:
        await callback.message.edit_text(
            "❌ Нельзя удалить.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_admins")]
                ]
            ),
        )
        return

    label = _admin_label(admin)
    await callback.message.edit_text(
        f"Удалить администратора?\n\n<b>{label}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да",
                        callback_data=f"admin_del_yes:{uid}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Нет",
                        callback_data="admin_remove_list",
                    ),
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith("admin_del_yes:"))
async def admin_del_yes(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    try:
        uid = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    async with AsyncSessionLocal() as session:
        ok = await BotAdminRepository(session).remove(uid)

    if ok:
        await callback.message.edit_text(
            "✅ Администратор удалён.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ К списку",
                            callback_data="settings_admins",
                        )
                    ]
                ]
            ),
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось удалить (владелец или не найден).",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ К списку",
                            callback_data="settings_admins",
                        )
                    ]
                ]
            ),
        )
