import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from database.channel_repository import ChannelRepository
from database.db import AsyncSessionLocal
from database.user_settings_repository import UserSettingsRepository
from keyboards.menu import main_menu
from states.admin import AdminStates
from services.channel_access import (
    CHANNEL_ACCESS_DENIED_TEXT,
    user_owns_channel_id,
    verify_channel_access,
)
from services.channel_admin_ops import (
    demote_channel_admin,
    get_bot_promote_status,
    list_human_admins,
    promote_channel_admin,
)

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
            if not await user_owns_channel_id(callback.from_user.id, channel_id):
                await callback.message.edit_text(
                    "🚫 <b>У вас нет прав для управления данным каналом.</b>",
                    parse_mode="HTML",
                    reply_markup=settings_keyboard(),
                )
                return
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


# ─── Администраторы канала ─────────────────────────────

NO_CHANNEL_TEXT = (
    "👤 <b>Администраторы</b>\n\n"
    "У вас пока нет подключённых каналов.\n\n"
    "Сначала добавьте канал:\n"
    "⚙️ Настройки → 📺 Каналы → ➕ Добавить канал."
)

INSUFFICIENT_PROMOTE_TEXT = (
    "⚠️ <b>Недостаточно прав</b>\n\n"
    "Для управления администраторами канала необходимо "
    "предоставить PugBot дополнительное разрешение.\n\n"
    "<b>Что нужно сделать:</b>\n\n"
    "1️⃣ Откройте настройки вашего Telegram-канала.\n"
    "2️⃣ Перейдите в раздел <b>Администраторы</b>.\n"
    "3️⃣ Выберите <b>PugBot</b>.\n"
    "4️⃣ Включите разрешение:\n"
    "✅ <b>Назначать администраторов</b>\n\n"
    "После этого вернитесь в PugBot и нажмите кнопку проверки.\n\n"
    "После выдачи разрешения вы сможете:\n"
    "✅ назначать администраторов;\n"
    "✅ снимать администраторов;\n"
    "✅ управлять администраторами канала прямо из PugBot."
)

ADMINS_HUB_TEXT = (
    "👤 <b>Администраторы</b>\n\n"
    "📺 <b>Канал</b>\n"
    "{title}\n\n"
    "Здесь вы можете управлять администраторами\n"
    "подключённого канала."
)

BOT_NOT_ADMIN_TEXT = (
    "⚠️ <b>PugBot больше не является администратором "
    "данного канала.</b>\n\n"
    "Добавьте PugBot обратно в канал\n"
    "и повторите попытку."
)

USER_LOST_RIGHTS_TEXT = (
    "🚫 <b>У вас больше нет прав для управления "
    "данным каналом.</b>\n\n"
    "Попросите владельца канала снова предоставить\n"
    "вам права администратора."
)


def _promote_rights_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Проверить права",
                    callback_data="admin_check_rights",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
                InlineKeyboardButton(
                    text="🏠 Главное меню", callback_data="settings_to_menu"
                ),
            ],
        ]
    )


def _admins_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
            [InlineKeyboardButton(text="➖ Удалить", callback_data="admin_remove_list")],
            [
                InlineKeyboardButton(
                    text="📋 Список администраторов",
                    callback_data="admin_list",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
                InlineKeyboardButton(
                    text="🏠 Главное меню", callback_data="settings_to_menu"
                ),
            ],
        ]
    )


def _admin_person_label(admin) -> str:
    if admin.username:
        name = f"{admin.full_name} (@{admin.username})"
    else:
        name = admin.full_name
    if admin.is_creator:
        return f"👑 {name}"
    if admin.is_bot:
        return f"🤖 {name}"
    return f"👤 {name}"


def _format_admins_list(admins: list, *, title: str) -> str:
    total = len(admins)
    if admins:
        lines = "\n".join(_admin_person_label(a) for a in admins)
    else:
        lines = "Список пуст."
    return (
        f"📋 <b>Администраторы канала</b>\n\n"
        f"📺 <b>Канал</b>\n"
        f"{title}\n\n"
        f"Всего: <b>{total}</b>\n\n"
        f"{lines}\n\n"
        f"────────────"
    )


async def _user_channels(user_id: int):
    async with AsyncSessionLocal() as session:
        repo = ChannelRepository(session)
        return await repo.get_channels_for_user(user_id)


async def _resolve_working_channel(user_id: int):
    """Выбрать канал: default → единственный → None (нужен выбор)."""
    channels = await _user_channels(user_id)
    if not channels:
        return None, []

    async with AsyncSessionLocal() as session:
        settings = await UserSettingsRepository(session).get(user_id)
        default_id = settings.default_channel_id if settings else None

    if default_id is not None:
        for ch in channels:
            if ch.id == default_id:
                return ch, channels

    if len(channels) == 1:
        return channels[0], channels

    return None, channels


async def _store_channel_ctx(state: FSMContext, channel) -> None:
    await state.update_data(
        admin_channel_id=channel.id,
        admin_chat_id=channel.telegram_chat_id,
        admin_channel_title=channel.title or "Канал",
    )


async def _load_channel_ctx(state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("admin_chat_id")
    title = data.get("admin_channel_title") or "Канал"
    return chat_id, title


async def _ensure_promote_or_prompt(target: Message, bot, chat_id: int, *, title: str) -> bool:
    status = await get_bot_promote_status(bot, chat_id)
    if status.can_promote:
        return True
    if status.detail in ("left", "forbidden", "not_admin", "bad_request"):
        body = BOT_NOT_ADMIN_TEXT
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Проверить права",
                        callback_data="admin_check_rights",
                    )
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
                    InlineKeyboardButton(
                        text="🏠 Главное меню", callback_data="settings_to_menu"
                    ),
                ],
            ]
        )
    else:
        body = INSUFFICIENT_PROMOTE_TEXT
        kb = _promote_rights_keyboard()
    await target.edit_text(body, parse_mode="HTML", reply_markup=kb)
    return False


def _access_denied_text(reason: str | None) -> str:
    if reason in ("bot_missing",):
        return BOT_NOT_ADMIN_TEXT
    if reason in ("not_tg_admin", "not_owner"):
        return USER_LOST_RIGHTS_TEXT
    return CHANNEL_ACCESS_DENIED_TEXT


async def _open_admins_hub(target: Message, *, title: str) -> None:
    await target.edit_text(
        ADMINS_HUB_TEXT.format(title=title),
        parse_mode="HTML",
        reply_markup=_admins_hub_keyboard(),
    )


def _channel_pick_keyboard(channels) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📺 {ch.title or 'Канал'}",
                    callback_data=f"admin_pick_ch:{ch.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back"),
            InlineKeyboardButton(
                text="🏠 Главное меню", callback_data="settings_to_menu"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "settings_admins")
async def settings_admins(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    channel, channels = await _resolve_working_channel(callback.from_user.id)
    if not channels:
        await callback.message.edit_text(
            NO_CHANNEL_TEXT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=_nav_rows(
                    [
                        InlineKeyboardButton(
                            text="➕ Добавить канал",
                            callback_data="channels_add",
                        )
                    ]
                )
            ),
        )
        return

    if channel is None:
        await callback.message.edit_text(
            "👤 <b>Администраторы</b>\n\n"
            "Выберите канал для управления администраторами:",
            parse_mode="HTML",
            reply_markup=_channel_pick_keyboard(channels),
        )
        return

    await _store_channel_ctx(state, channel)
    access = await verify_channel_access(
        callback.bot,
        callback.from_user.id,
        channel_id=channel.id,
        live_telegram=True,
    )
    if not access.ok:
        await callback.message.edit_text(
            _access_denied_text(access.reason),
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )
        return
    ok = await _ensure_promote_or_prompt(
        callback.message,
        callback.bot,
        channel.telegram_chat_id,
        title=channel.title or "Канал",
    )
    if ok:
        await _open_admins_hub(callback.message, title=channel.title or "Канал")


@router.callback_query(F.data.startswith("admin_pick_ch:"))
async def admin_pick_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return
    try:
        ch_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    channels = await _user_channels(callback.from_user.id)
    channel = next((c for c in channels if c.id == ch_id), None)
    if channel is None:
        await callback.message.edit_text(
            "❌ Канал не найден или недоступен.",
            reply_markup=settings_keyboard(),
        )
        return

    await _store_channel_ctx(state, channel)
    ok = await _ensure_promote_or_prompt(
        callback.message,
        callback.bot,
        channel.telegram_chat_id,
        title=channel.title or "Канал",
    )
    if ok:
        await _open_admins_hub(callback.message, title=channel.title or "Канал")


@router.callback_query(F.data == "admin_check_rights")
async def admin_check_rights(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        channel, channels = await _resolve_working_channel(callback.from_user.id)
        if not channels:
            await callback.message.edit_text(
                NO_CHANNEL_TEXT,
                parse_mode="HTML",
                reply_markup=settings_keyboard(),
            )
            return
        if channel is None:
            await callback.message.edit_text(
                "👤 <b>Администраторы</b>\n\n"
                "Выберите канал для управления администраторами:",
                parse_mode="HTML",
                reply_markup=_channel_pick_keyboard(channels),
            )
            return
        await _store_channel_ctx(state, channel)
        chat_id = channel.telegram_chat_id
        title = channel.title or "Канал"

    status = await get_bot_promote_status(callback.bot, chat_id)
    if status.can_promote:
        await _open_admins_hub(callback.message, title=title)
        return

    await callback.message.edit_text(
        INSUFFICIENT_PROMOTE_TEXT,
        parse_mode="HTML",
        reply_markup=_promote_rights_keyboard(),
    )


@router.callback_query(F.data == "admin_list")
async def admin_list(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await callback.message.edit_text(
            "❌ Сначала откройте раздел заново.",
            reply_markup=settings_keyboard(),
        )
        return

    access = await verify_channel_access(
        callback.bot,
        callback.from_user.id,
        telegram_chat_id=chat_id,
        live_telegram=True,
    )
    if not access.ok:
        await callback.message.edit_text(
            _access_denied_text(access.reason),
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )
        return

    if not await _ensure_promote_or_prompt(
        callback.message, callback.bot, chat_id, title=title
    ):
        return

    try:
        admins = await list_human_admins(callback.bot, chat_id)
    except Exception:
        logger.exception("list admins chat=%s", chat_id)
        await callback.message.edit_text(
            "❌ <b>Не удалось получить список</b>\n\n"
            "Проверьте, что бот остаётся администратором канала.",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        return

    await callback.message.edit_text(
        _format_admins_list(admins, title=title),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_hub_back",
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data == "admin_hub_back")
async def admin_hub_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    # Сохраняем контекст канала, сбрасываем только FSM-состояние ввода
    data = await state.get_data()
    await state.set_state(None)
    await state.set_data(data)
    _, title = await _load_channel_ctx(state)
    await _open_admins_hub(callback.message, title=title)


@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await callback.message.edit_text(
            "❌ Сначала откройте раздел заново.",
            reply_markup=settings_keyboard(),
        )
        return

    access = await verify_channel_access(
        callback.bot,
        callback.from_user.id,
        telegram_chat_id=chat_id,
        live_telegram=True,
    )
    if not access.ok:
        await callback.message.edit_text(
            _access_denied_text(access.reason),
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )
        return

    if not await _ensure_promote_or_prompt(
        callback.message, callback.bot, chat_id, title=title
    ):
        return

    await state.set_state(AdminStates.waiting_new_admin)
    await callback.message.edit_text(
        "➕ <b>Добавление администратора</b>\n\n"
        f"📺 <b>Канал</b>\n"
        f"{title}\n\n"
        "Перешлите сообщение пользователя\n"
        "или отправьте его Telegram ID\n"
        "или @username.\n\n"
        "ℹ️ Пользователь должен хотя бы один раз\n"
        "открыть диалог с PugBot.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="admin_hub_back",
                    )
                ]
            ]
        ),
    )


@router.message(AdminStates.waiting_new_admin)
async def admin_add_receive(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await state.clear()
        await message.answer(
            "❌ Сессия устарела. Откройте ⚙️ Настройки → 👤 Администраторы.",
            parse_mode="HTML",
        )
        return

    access = await verify_channel_access(
        message.bot,
        message.from_user.id,
        telegram_chat_id=chat_id,
        live_telegram=True,
    )
    if not access.ok:
        await state.clear()
        await message.answer(
            _access_denied_text(access.reason),
            parse_mode="HTML",
        )
        return

    status = await get_bot_promote_status(message.bot, chat_id)
    if not status.can_promote:
        await state.clear()
        if status.detail in ("left", "forbidden", "not_admin", "bad_request"):
            body = BOT_NOT_ADMIN_TEXT
        else:
            body = INSUFFICIENT_PROMOTE_TEXT
        await message.answer(
            body,
            parse_mode="HTML",
            reply_markup=_promote_rights_keyboard(),
        )
        return

    user_id = None
    display_name = None
    username = None

    if message.forward_from is not None:
        src = message.forward_from
        user_id = src.id
        display_name = src.full_name
        username = src.username
    elif message.forward_sender_name:
        await message.answer(
            "❌ Не удалось определить пользователя "
            "(скрытый аккаунт при пересылке).\n"
            "Отправьте Telegram ID."
        )
        return
    elif message.text:
        raw = message.text.strip()
        if raw.startswith("@"):
            try:
                chat = await message.bot.get_chat(raw)
                user_id = chat.id
                display_name = getattr(chat, "full_name", None) or (
                    getattr(chat, "first_name", None) or raw
                )
                username = getattr(chat, "username", None) or raw.lstrip("@")
            except Exception as exc:
                logger.warning("username lookup failed: %s", exc)
                await message.answer(
                    "❌ <b>Пользователь не найден</b>\n\n"
                    "Проверьте @username или отправьте Telegram ID.",
                    parse_mode="HTML",
                )
                return
        elif raw.lstrip("-").isdigit():
            user_id = int(raw)
            try:
                chat = await message.bot.get_chat(user_id)
                display_name = getattr(chat, "full_name", None) or getattr(
                    chat, "first_name", None
                )
                username = getattr(chat, "username", None)
            except Exception:
                display_name = None
                username = None
        else:
            await message.answer(
                "❌ Не распознано. Перешлите сообщение или отправьте ID."
            )
            return
    else:
        await message.answer("❌ Отправьте текст или перешлите сообщение.")
        return

    if user_id is None:
        await message.answer("❌ Не удалось определить ID.")
        return

    if user_id == message.from_user.id:
        await message.answer("ℹ️ Вы уже управляете каналом через PugBot.")
        return

    try:
        await promote_channel_admin(message.bot, chat_id, user_id)
    except TelegramForbiddenError:
        await message.answer(
            "❌ <b>Недостаточно прав</b>\n\n"
            "PugBot не может назначить администратора.\n"
            "Проверьте разрешение «Назначать администраторов».",
            parse_mode="HTML",
            reply_markup=_promote_rights_keyboard(),
        )
        await state.clear()
        return
    except TelegramBadRequest as e:
        err = (getattr(e, "message", None) or str(e)).lower()
        if "user not found" in err or "peer" in err:
            detail = (
                "Пользователь не найден или ещё не начинал диалог с ботом.\n"
                "Попросите его написать боту /start."
            )
        elif "can't promote" in err or "not enough rights" in err:
            detail = (
                "Нельзя назначить этого пользователя.\n"
                "Возможно, он уже администратор с более высокими правами."
            )
        else:
            detail = "Не удалось назначить администратора. Попробуйте позже."
        await message.answer(
            f"❌ <b>Не удалось добавить</b>\n\n{detail}",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        await state.clear()
        return
    except Exception:
        logger.exception("promote failed chat=%s user=%s", chat_id, user_id)
        await message.answer(
            "❌ <b>Не удалось добавить</b>\n\nПопробуйте позже.",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        await state.clear()
        return

    await state.set_state(None)
    await state.update_data(admin_chat_id=chat_id, admin_channel_title=title)

    if display_name and username:
        who = f"👤 {display_name}\n(@{username})"
    elif display_name:
        who = f"👤 {display_name}"
    elif username:
        who = f"👤 @{username}"
    else:
        who = f"👤 ID: {user_id}"

    logger.info(
        "channel_admin_promote by=%s target=%s chat_id=%s title=%r",
        message.from_user.id,
        user_id,
        chat_id,
        title,
    )
    await message.answer(
        "✅ <b>Администратор успешно добавлен.</b>\n\n"
        f"{who}\n\n"
        f"📺 <b>Канал</b>\n"
        f"{title}\n\n"
        "Пользователь получил права администратора канала.",
        parse_mode="HTML",
        reply_markup=_admins_hub_keyboard(),
    )


@router.callback_query(F.data == "admin_remove_list")
async def admin_remove_list(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await callback.message.edit_text(
            "❌ Сначала откройте раздел заново.",
            reply_markup=settings_keyboard(),
        )
        return

    access = await verify_channel_access(
        callback.bot,
        callback.from_user.id,
        telegram_chat_id=chat_id,
        live_telegram=True,
    )
    if not access.ok:
        await callback.message.edit_text(
            _access_denied_text(access.reason),
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )
        return

    if not await _ensure_promote_or_prompt(
        callback.message, callback.bot, chat_id, title=title
    ):
        return

    try:
        admins = await list_human_admins(callback.bot, chat_id)
    except Exception:
        logger.exception("list for remove chat=%s", chat_id)
        await callback.message.edit_text(
            "❌ Не удалось получить список администраторов.",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        return

    removable = [a for a in admins if not a.is_creator and not a.is_bot]
    if not removable:
        await callback.message.edit_text(
            "ℹ️ <b>Сейчас нет администраторов,</b>\n"
            "которых можно снять.\n\n"
            "Владелец канала и Telegram-боты\n"
            "не могут быть удалены через PugBot.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ Назад",
                            callback_data="admin_hub_back",
                        )
                    ]
                ]
            ),
        )
        return

    rows: list[list[InlineKeyboardButton]] = []
    for a in removable:
        label = a.full_name
        if a.username:
            label = f"{a.full_name} (@{a.username})"
        if len(label) > 60:
            label = label[:57] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin_del_ask:{a.user_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_hub_back")]
    )

    await callback.message.edit_text(
        f"➖ <b>Удалить администратора</b>\n\n"
        f"Канал: <b>{title}</b>\n\n"
        f"Выберите, кого снять:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("admin_del_ask:"))
async def admin_del_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    try:
        uid = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await callback.message.edit_text(
            "❌ Сначала откройте раздел заново.",
            reply_markup=settings_keyboard(),
        )
        return

    label = f"ID {uid}"
    try:
        admins = await list_human_admins(callback.bot, chat_id)
        for a in admins:
            if a.user_id == uid:
                label = _admin_person_label(a)
                if a.is_creator:
                    await callback.message.edit_text(
                        "👑 Владельца канала удалить нельзя.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="⬅️ Назад",
                                        callback_data="admin_remove_list",
                                    )
                                ]
                            ]
                        ),
                    )
                    return
                break
    except Exception:
        pass

    await callback.message.edit_text(
        f"➖ <b>Снять администратора?</b>\n\n"
        f"{label}\n\n"
        f"Канал: <b>{title}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, снять",
                        callback_data=f"admin_del_yes:{uid}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_remove_list",
                    )
                ],
            ]
        ),
    )


@router.callback_query(F.data.startswith("admin_del_yes:"))
async def admin_del_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return
    try:
        uid = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    chat_id, title = await _load_channel_ctx(state)
    if chat_id is None:
        await callback.message.edit_text(
            "❌ Сначала откройте раздел заново.",
            reply_markup=settings_keyboard(),
        )
        return

    access = await verify_channel_access(
        callback.bot,
        callback.from_user.id,
        telegram_chat_id=chat_id,
        live_telegram=True,
    )
    if not access.ok:
        await callback.message.edit_text(
            _access_denied_text(access.reason),
            parse_mode="HTML",
            reply_markup=settings_keyboard(),
        )
        return

    status = await get_bot_promote_status(callback.bot, chat_id)
    if not status.can_promote:
        body = (
            BOT_NOT_ADMIN_TEXT
            if status.detail in ("left", "forbidden", "not_admin", "bad_request")
            else INSUFFICIENT_PROMOTE_TEXT
        )
        await callback.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=_promote_rights_keyboard(),
        )
        return

    try:
        await demote_channel_admin(callback.bot, chat_id, uid)
    except TelegramForbiddenError:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "PugBot не может снять этого администратора.",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        return
    except TelegramBadRequest as e:
        err = (getattr(e, "message", None) or str(e)).lower()
        if "can't demote" in err or "not enough" in err or "creator" in err:
            detail = (
                "Нельзя снять этого администратора.\n"
                "Возможно, он владелец или назначен с более высокими правами."
            )
        else:
            detail = "Не удалось снять администратора. Попробуйте позже."
        await callback.message.edit_text(
            f"❌ <b>Не удалось удалить</b>\n\n{detail}",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        return
    except Exception:
        logger.exception("demote failed chat=%s user=%s", chat_id, uid)
        await callback.message.edit_text(
            "❌ <b>Не удалось удалить</b>\n\nПопробуйте позже.",
            parse_mode="HTML",
            reply_markup=_admins_hub_keyboard(),
        )
        return

    logger.info(
        "channel_admin_demote by=%s target=%s chat_id=%s title=%r",
        callback.from_user.id if callback.from_user else None,
        uid,
        chat_id,
        title,
    )
    await callback.message.edit_text(
        "✅ <b>Администратор успешно удалён.</b>\n\n"
        f"📺 <b>Канал</b>\n"
        f"{title}",
        parse_mode="HTML",
        reply_markup=_admins_hub_keyboard(),
    )
