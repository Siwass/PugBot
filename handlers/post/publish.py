import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from database.db import AsyncSessionLocal
from database.post_repository import PostRepository
from keyboards.menu import main_menu
from services.publishing import publish_post as publish_service
from utils.ux_errors import (
    STALE_MENU_TEXT,
    error_keyboard,
    format_publish_error,
    stale_menu_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)


def _retry_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Повторить публикацию",
                    callback_data=f"retry_publish:{post_id}",
                )
            ]
        ]
    )


def _friendly_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "forbidden" in text or "bot is not a member" in text:
        return (
            "❌ Бот не может писать в канал.\n\n"
            "Проверьте, что бот — администратор с правом публикации."
        )
    if "chat not found" in text:
        return "❌ Канал не найден. Проверьте подключение в Настройках."
    if "need administrator" in text or "not enough rights" in text:
        return "❌ Недостаточно прав администратора в канале."
    return "❌ Не удалось опубликовать пост. Попробуйте ещё раз позже."


@router.callback_query(F.data == "confirm_publish")
async def publish_post(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    post_id = data.get("post_id")

    if not post_id:
        await callback.message.answer(
            STALE_MENU_TEXT,
            parse_mode="HTML",
            reply_markup=stale_menu_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or (
            callback.from_user and post.author_id != callback.from_user.id
        ):
            await callback.message.answer("❌ Черновик не найден.")
            return

        try:
            message_id, chat_id = await publish_service(callback.bot, post)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.error("Ошибка публикации поста %s: %s", post.id, exc)
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.message.answer(
                _friendly_error(exc),
                reply_markup=_retry_keyboard(post.id),
            )
            return
        except Exception as exc:
            logger.exception("Не удалось опубликовать пост %s", post.id)
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.message.answer(
                _friendly_error(exc),
                reply_markup=_retry_keyboard(post.id),
            )
            return

        from services.scheduled_publisher import get_local_now
        from datetime import timedelta

        published_at = get_local_now()
        await repo.mark_published(
            post.id,
            telegram_message_id=message_id,
            telegram_chat_id=chat_id,
            published_at=published_at,
        )
        if post.auto_delete_hours:
            await repo.set_auto_delete(
                post.id,
                post.auto_delete_hours,
                auto_delete_at=published_at + timedelta(hours=post.auto_delete_hours),
            )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Опубликовано",
                            callback_data="published",
                        )
                    ]
                ]
            )
        )
    except Exception:
        pass

    await state.clear()

    if callback.from_user is not None:
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="✅ Пост успешно опубликован!\n\nЧто хотите сделать дальше?",
            reply_markup=main_menu,
        )


@router.callback_query(F.data.startswith("retry_publish:"))
async def retry_publish(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    if callback.from_user is None:
        return

    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer("❌ Некорректные данные.")
        return

    async with AsyncSessionLocal() as session:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)

        if not post or post.author_id != callback.from_user.id:
            await callback.message.answer("❌ Пост не найден.")
            return

        if post.status not in ("failed", "draft"):
            await callback.message.answer(
                "ℹ️ Повтор доступен для постов со статусом failed/draft."
            )
            return

        # Сбрасываем ошибку, пробуем снова
        post.status = "draft"
        post.error_message = None
        await session.commit()

        try:
            message_id, chat_id = await publish_service(callback.bot, post)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.message.answer(
                _friendly_error(exc),
                reply_markup=_retry_keyboard(post.id),
            )
            return
        except Exception as exc:
            await repo.mark_publish_failed(post.id, error_message=str(exc))
            await callback.message.answer(
                _friendly_error(exc),
                reply_markup=_retry_keyboard(post.id),
            )
            return

        from services.scheduled_publisher import get_local_now
        from datetime import timedelta

        published_at = get_local_now()
        await repo.mark_published(
            post.id,
            telegram_message_id=message_id,
            telegram_chat_id=chat_id,
            published_at=published_at,
        )
        if post.auto_delete_hours:
            await repo.set_auto_delete(
                post.id,
                post.auto_delete_hours,
                auto_delete_at=published_at + timedelta(hours=post.auto_delete_hours),
            )

    await state.clear()
    await callback.message.answer(
        "✅ Пост успешно опубликован!",
        reply_markup=main_menu,
    )


@router.callback_query(F.data == "published")
async def already_published(callback: CallbackQuery):
    await callback.answer(
        "Этот пост уже опубликован ✅",
        show_alert=True,
    )
