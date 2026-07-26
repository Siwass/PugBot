import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import (
    EDIT_CONTEXT_DRAFT,
    show_draft_list,
    show_draft_preview,
    safe_edit_text,
)
from keyboards.menu import main_menu
from keyboards.formatting import formatting_keyboard, format_tools_keyboard
from keyboards.buttons import buttons_keyboard
from keyboards.skip import skip_keyboard
from services.publishing import publish_post
from services.channel_resolver import get_user_channels, get_channel_chat_id
from utils.ux_errors import (
    STALE_MENU_TEXT,
    error_keyboard,
    format_publish_error,
    stale_menu_keyboard,
)
from states.post import CreatePost

router = Router()
logger = logging.getLogger(__name__)


def _parse_id(data: str | None, prefix: str) -> int | None:
    if not data or not data.startswith(prefix):
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


async def _load_draft(
    post_id: int,
    user_id: int,
) -> tuple[object | None, str | None]:
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != user_id:
        return None, "❌ Черновик не найден."

    if post.status != "draft":
        return None, f"ℹ️ Этот пост уже не черновик (статус: {post.status})."

    return post, None


# ─── Список ────────────────────────────────────────────


@router.message(F.text == "📂 Черновики")
async def drafts(message: Message, state: FSMContext):
    if message.from_user is None:
        return
    await state.clear()
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    await show_draft_list(
        message,
        author_id=message.from_user.id,
        restore_main_menu=False,
    )


@router.callback_query(F.data == "drafts_back")
async def drafts_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None:
        return
    await state.clear()
    # Назад к списку — без главного меню (раздел ещё открыт)
    await show_draft_list(
        callback,
        author_id=callback.from_user.id,
        restore_main_menu=False,
    )


@router.callback_query(F.data == "drafts_to_menu")
async def drafts_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    if callback.message is not None and isinstance(callback.message, Message):
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu,
        )


# ─── Открытие карточки ─────────────────────────────────


@router.callback_query(F.data.startswith("draft_open_"))
@router.callback_query(F.data.startswith("draft_open:"))
async def open_draft(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or callback.data is None:
        return

    raw = callback.data
    if raw.startswith("draft_open_"):
        post_id = _parse_id(raw, "draft_open_")
    else:
        post_id = _parse_id(raw, "draft_open:")
    if post_id is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post, err = await _load_draft(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await state.clear()
    await state.update_data(
        post_id=post.id,
        original_text=post.text or "",
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await show_draft_preview(callback, state, post_id=post.id)


# ─── Действия карточки ─────────────────────────────────


@router.callback_query(F.data.startswith("draft_edit_text_"))
async def draft_edit_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    post_id = _parse_id(callback.data, "draft_edit_text_")
    if post_id is None:
        return

    post, err = await _load_draft(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await state.update_data(
        post_id=post.id,
        original_text=post.text or "",
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await state.set_state(CreatePost.editing_text)
    await callback.message.answer(
        "✍️ Отправьте новый текст поста.\n\n"
        "Отправьте «-», чтобы оставить текущий текст."
    )


@router.callback_query(F.data.startswith("draft_format_"))
async def draft_format(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    post_id = _parse_id(callback.data, "draft_format_")
    if post_id is None:
        return

    post, err = await _load_draft(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await state.update_data(
        post_id=post.id,
        original_text=post.text or "",
        edit_context=EDIT_CONTEXT_DRAFT,
        format_screen=True,
    )
    from handlers.post.formatting import show_format_screen

    await show_format_screen(callback.message, state)


@router.callback_query(F.data.startswith("draft_media_"))
async def draft_media(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    post_id = _parse_id(callback.data, "draft_media_")
    if post_id is None:
        return

    post, err = await _load_draft(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await state.update_data(
        post_id=post.id,
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await state.set_state(CreatePost.waiting_media)
    await callback.message.answer(
        "📷 Отправьте фото или нажмите «Пропустить».",
        reply_markup=skip_keyboard,
    )


@router.callback_query(F.data.startswith("draft_buttons_"))
async def draft_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    post_id = _parse_id(callback.data, "draft_buttons_")
    if post_id is None:
        return

    post, err = await _load_draft(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await state.update_data(
        post_id=post.id,
        edit_context=EDIT_CONTEXT_DRAFT,
    )
    await state.set_state(CreatePost.waiting_buttons)
    await callback.message.answer(
        "🔗 Хотите добавить кнопку?",
        reply_markup=buttons_keyboard,
    )


@router.callback_query(F.data.startswith("draft_publish_"))
@router.callback_query(F.data.startswith("draft_publish:"))
async def draft_publish(callback: CallbackQuery, state: FSMContext):
    """Опубликовать черновик сейчас (без промежуточного предпросмотра)."""
    if callback.from_user is None or callback.data is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post_id = _parse_id(callback.data, "draft_publish_")
    if post_id is None:
        post_id = _parse_id(callback.data, "draft_publish:")
    if post_id is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    msg = callback.message if isinstance(callback.message, Message) else None

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or post.author_id != callback.from_user.id:
            await callback.answer()
            if msg:
                await msg.answer(
                    STALE_MENU_TEXT,
                    parse_mode="HTML",
                    reply_markup=stale_menu_keyboard(),
                )
            return

        if post.status != "draft":
            await callback.answer()
            if msg:
                await msg.answer(
                    STALE_MENU_TEXT,
                    parse_mode="HTML",
                    reply_markup=stale_menu_keyboard(),
                )
            await state.clear()
            return

        # Канал: из поста → default пользователя → первый канал пользователя
        chat_id = None
        if post.channel_id:
            chat_id = await get_channel_chat_id(post.channel_id)
        if chat_id is None:
            channels = await get_user_channels(callback.from_user.id)
            if channels:
                chat_id = channels[0].telegram_chat_id
                await repo.update_channel(post.id, channels[0].id)
                post.channel_id = channels[0].id

        if chat_id is None:
            await callback.answer()
            if msg:
                await msg.answer(
                    format_publish_error(ValueError("Канал не настроен")),
                    parse_mode="HTML",
                    reply_markup=error_keyboard(back_callback="drafts_back"),
                )
            return

        try:
            message_id, resolved_chat = await publish_post(
                callback.bot, post, chat_id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
            )
        except TelegramForbiddenError as exc:
            logger.error("Нет прав публикации черновика %s: %s", post.id, exc)
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.answer()
            if msg:
                await msg.answer(
                    format_publish_error(exc),
                    parse_mode="HTML",
                    reply_markup=error_keyboard(
                        retry_callback=f"draft_publish_{post.id}",
                        back_callback="drafts_back",
                    ),
                )
            return
        except Exception as exc:
            logger.exception("Ошибка публикации черновика %s", post.id)
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.answer()
            if msg:
                await msg.answer(
                    format_publish_error(exc),
                    parse_mode="HTML",
                    reply_markup=error_keyboard(
                        retry_callback=f"draft_publish_{post.id}",
                        back_callback="drafts_back",
                    ),
                )
            return

        from datetime import timedelta
        from services.scheduled_publisher import get_local_now

        published_at = get_local_now()
        published = await repo.mark_published(
            post_id,
            telegram_message_id=message_id,
            telegram_chat_id=resolved_chat,
            published_at=published_at,
        )
        if post.auto_delete_hours:
            await repo.set_auto_delete(
                post_id,
                post.auto_delete_hours,
                auto_delete_at=published_at
                + timedelta(hours=post.auto_delete_hours),
            )

    if not published:
        await callback.answer()
        if msg:
            await msg.answer(
                format_publish_error(RuntimeError("status")),
                parse_mode="HTML",
                reply_markup=error_keyboard(back_callback="drafts_back"),
            )
        return

    await state.clear()
    await callback.answer("✅ Опубликовано")
    if msg is not None:
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await msg.answer(
            "✅ Черновик успешно опубликован.",
            reply_markup=main_menu,
        )


@router.callback_query(F.data.startswith("draft_delete_"))
@router.callback_query(F.data.startswith("draft_delete:"))
async def draft_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None:
        return

    post_id = _parse_id(callback.data, "draft_delete_")
    if post_id is None:
        post_id = _parse_id(callback.data, "draft_delete:")
    if post_id is None:
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post or post.author_id != callback.from_user.id:
            await callback.answer("❌ Черновик не найден.", show_alert=True)
            return
        await repo.delete(post_id)

    await state.clear()
    if callback.message is not None and isinstance(callback.message, Message):
        await callback.message.answer(
            "✅ Черновик удалён.",
            reply_markup=main_menu,
        )


@router.callback_query(F.data == "delete_all_drafts")
async def delete_all_drafts(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        posts = await repo.get_drafts(author_id=callback.from_user.id)
        for post in posts:
            await repo.delete(post.id)

    await state.clear()
    await callback.message.answer(
        "✅ Все черновики удалены.",
        reply_markup=main_menu,
    )
