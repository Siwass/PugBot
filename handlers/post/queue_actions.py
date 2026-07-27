import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from handlers.post.preview_service import (
    EDIT_CONTEXT_QUEUE,
    QUEUE_NOT_SCHEDULED_MESSAGE,
    safe_edit_text,
    show_queue_list,
    show_queue_preview,
)
from states.post import CreatePost
from utils.ux_errors import (
    STALE_MENU_TEXT,
    error_keyboard,
    format_publish_error,
    stale_menu_keyboard,
)
from keyboards.buttons import buttons_keyboard
from keyboards.formatting import formatting_keyboard, format_tools_keyboard
from keyboards.skip import skip_keyboard
from keyboards.menu import main_menu
from services.publishing import publish_post

router = Router()
logger = logging.getLogger(__name__)


async def _load_scheduled_post(
    post_id: int,
    user_id: int,
) -> tuple[object | None, str | None]:
    """Возвращает (post, error_alert)."""
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

    if not post or post.author_id != user_id:
        return None, "❌ Пост не найден."

    if post.status != "scheduled":
        return None, QUEUE_NOT_SCHEDULED_MESSAGE

    return post, None


def _parse_id(data: str | None, prefix: str) -> int | None:
    if not data or not data.startswith(prefix):
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


@router.callback_query(F.data.startswith("queue_publish_"))
async def queue_publish(callback: CallbackQuery):
    post_id = _parse_id(callback.data, "queue_publish_")
    if post_id is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    if callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    # Загружаем свежий пост из БД (текст + media + channel)
    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or post.author_id != callback.from_user.id:
            await callback.answer("❌ Пост не найден.", show_alert=True)
            return

        if post.status not in ("scheduled", "draft", "failed"):
            await callback.answer(
                f"ℹ️ Нельзя опубликовать пост со статусом {post.status}.",
                show_alert=True,
            )
            return

        try:
            message_id, chat_id = await publish_post(callback.bot, post)
        except TelegramForbiddenError as exc:
            logger.error(
                "Нет прав публикации в канал для поста %s (из очереди): %s",
                post.id,
                exc,
            )
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.answer(
                "❌ Бот не может писать в канал. Проверьте права администратора.",
                show_alert=True,
            )
            return
        except TelegramBadRequest as exc:
            logger.error(
                "BadRequest при публикации поста %s из очереди: %s",
                post.id,
                exc,
            )
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.answer(
                f"❌ Ошибка Telegram: {exc.message}",
                show_alert=True,
            )
            return
        except Exception as exc:
            logger.exception(
                "Не удалось опубликовать пост %s из очереди",
                post.id,
            )
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.answer()
            if isinstance(callback.message, Message):
                await callback.message.answer(
                    format_publish_error(exc),
                    parse_mode="HTML",
                    reply_markup=error_keyboard(
                        retry_callback=f"queue_publish_{post.id}",
                        back_callback="queue_back",
                    ),
                )
            return

        from services.scheduled_publisher import get_local_now

        published = await repo.mark_published(
            post_id,
            telegram_message_id=message_id,
            telegram_chat_id=chat_id,
            published_at=get_local_now(),
        )

    if not published:
        await callback.answer(
            "❌ Не удалось обновить статус поста.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Опубликовано", show_alert=False)

    # Уведомление + возврат главного меню
    if callback.message is not None and isinstance(callback.message, Message):
        await callback.message.answer(
            "✅ Пост успешно опубликован из очереди.",
            reply_markup=main_menu,
        )


@router.callback_query(F.data.startswith("queue_edit_text_"))
async def queue_edit_text(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_id(callback.data, "queue_edit_text_")
    if post_id is None or callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post, err = await _load_scheduled_post(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer()

    await state.set_state(CreatePost.editing_text)
    await state.update_data(
        post_id=post_id,
        edit_context=EDIT_CONTEXT_QUEUE,
        original_text=post.text or "",
    )

    current = post.text or ""
    hint = f"\n\nТекущий текст:\n{current}" if current else ""
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "✍️ Отправьте новый текст поста." + hint
        )


@router.callback_query(F.data.startswith("queue_format_"))
async def queue_format(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_id(callback.data, "queue_format_")
    if post_id is None or callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post, err = await _load_scheduled_post(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer()

    await state.update_data(
        post_id=post_id,
        edit_context=EDIT_CONTEXT_QUEUE,
        original_text=post.text or "",
        format_screen=True,
    )
    await state.set_state(CreatePost.formatting)

    text = post.text or ""
    body = (
        f"📝 <b>Текущий текст</b>\n\n{text}"
        if text
        else "📝 <b>Текущий текст</b>\n\n<i>(пусто)</i>"
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(
            body,
            parse_mode="HTML",
            reply_markup=format_tools_keyboard,
        )


@router.callback_query(F.data.startswith("queue_media_"))
async def queue_media(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_id(callback.data, "queue_media_")
    if post_id is None or callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post, err = await _load_scheduled_post(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer()

    await state.set_state(CreatePost.editing_media)
    await state.update_data(
        post_id=post_id,
        edit_context=EDIT_CONTEXT_QUEUE,
    )

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "📷 Отправьте новое фото для поста.\n"
            "Или напишите «пропустить», чтобы убрать медиа.",
            reply_markup=skip_keyboard,
        )


@router.callback_query(F.data.startswith("queue_buttons_"))
async def queue_buttons(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_id(callback.data, "queue_buttons_")
    if post_id is None or callback.from_user is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    post, err = await _load_scheduled_post(post_id, callback.from_user.id)
    if err:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer()

    await state.set_state(CreatePost.waiting_buttons)
    await state.update_data(
        post_id=post_id,
        edit_context=EDIT_CONTEXT_QUEUE,
    )

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🔗 Редактирование кнопок.\n"
            "Можно добавить новые кнопки или нажать «⬅ Назад».",
            reply_markup=buttons_keyboard,
        )


# Старый callback queue_edit_ — на случай кэшированных сообщений
@router.callback_query(F.data.startswith("queue_edit_"))
async def queue_edit_legacy(callback: CallbackQuery, state: FSMContext):
    """Совместимость: queue_edit_<id> → то же, что редактирование текста."""
    if callback.data and callback.data.startswith("queue_edit_text_"):
        return  # обрабатывается отдельным handler выше по фильтру
    # rewrite to queue_edit_text_
    if callback.data is None:
        await callback.answer()
        return
    post_id = _parse_id(callback.data, "queue_edit_")
    if post_id is None:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return
    callback.data = f"queue_edit_text_{post_id}"
    await queue_edit_text(callback, state)


@router.callback_query(F.data.startswith("queue_delete_"))
async def queue_delete(callback: CallbackQuery):
    post_id = _parse_id(callback.data, "queue_delete_")
    if post_id is None:
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

        deleted = await repo.delete_from_queue(post_id)

    if not deleted:
        await callback.answer(
            "❌ Не удалось удалить пост из очереди.",
            show_alert=True,
        )
        return

    await callback.answer()

    if callback.message is not None and isinstance(callback.message, Message):
        await callback.message.answer(
            "✅ Пост удалён из очереди и возвращён в черновики.",
            reply_markup=main_menu,
        )


@router.callback_query(F.data == "queue_back")
async def queue_back(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку очереди."""
    await callback.answer()

    if callback.from_user is None or callback.message is None:
        return

    await state.clear()
    await show_queue_list(
        callback,
        author_id=callback.from_user.id,
        restore_main_menu=False,
    )
