import json
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.db import AsyncSessionLocal
from database.models import Post
from services.channel_resolver import get_publish_chat_id, get_channel_chat_id

logger = logging.getLogger(__name__)

# Лимит Telegram на caption у фото
TELEGRAM_CAPTION_LIMIT = 1024


def build_post_keyboard(post: Post) -> InlineKeyboardMarkup | None:
    if not post.buttons:
        return None

    buttons = json.loads(post.buttons)

    if not buttons:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button["text"],
                    url=button["url"],
                )
            ]
            for button in buttons
        ]
    )


def split_photo_caption(text: str | None) -> tuple[str | None, str | None]:
    """Разделить текст на caption и отдельное сообщение.

    Returns:
        (caption, separate_text)
        — если текст помещается в caption: (text, None)
        — если слишком длинный: (None, text)
        — если пустой: (None, None)
    """
    body = text or ""
    if not body:
        return None, None
    if len(body) <= TELEGRAM_CAPTION_LIMIT:
        return body, None
    return None, body


async def answer_photo_with_text(
    message: Message,
    photo: str,
    text: str | None,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> None:
    """Отправить фото в чат пользователя (превью), учитывая лимит caption."""
    caption, separate = split_photo_caption(text)

    if caption is not None:
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return

    await message.answer_photo(photo=photo)

    if separate:
        await message.answer(
            separate,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    elif reply_markup is not None:
        await message.answer("👆", reply_markup=reply_markup)


async def send_photo_with_text(
    bot: Bot,
    chat_id: int | str,
    photo: str,
    text: str | None,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> Message:
    """Отправить фото в канал/чат через Bot API, учитывая лимит caption.

    Returns:
        Сообщение с фото (основное для хранения message_id).
    """
    caption, separate = split_photo_caption(text)

    if caption is not None:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    result = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
    )

    if separate:
        await bot.send_message(
            chat_id=chat_id,
            text=separate,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    elif reply_markup is not None:
        await bot.send_message(
            chat_id=chat_id,
            text="👆",
            reply_markup=reply_markup,
        )

    return result


async def publish_post(
    bot: Bot,
    post: Post,
    chat_id: int | None = None,
    *,
    session_factory=AsyncSessionLocal,
) -> tuple[int, int]:
    """
    Публикует пост в канал.

    Returns:
        (telegram_message_id, telegram_chat_id)

    Raises:
        TelegramForbiddenError / TelegramBadRequest / Exception
    """
    if chat_id is None:
        if post.channel_id:
            chat_id = await get_channel_chat_id(
                post.channel_id, session_factory=session_factory
            )
        if chat_id is None:
            chat_id = await get_publish_chat_id(session_factory=session_factory)

    keyboard = build_post_keyboard(post)
    text = post.text or ""

    logger.debug(
        "Publishing post %s to chat %s",
        post.id,
        chat_id,
    )

    try:
        result: Message
        if post.media:
            media = json.loads(post.media)
            if media.get("type") != "photo" or not media.get("files"):
                raise ValueError("Поддерживается только публикация фотографии")

            result = await send_photo_with_text(
                bot,
                chat_id,
                media["files"][0],
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            result = await bot.send_message(
                chat_id=chat_id,
                text=text or " ",
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        message_id = result.message_id
        resolved_chat_id = int(result.chat.id)

        logger.info(
            "Пост %s успешно опубликован в чат %s (message_id=%s)",
            post.id,
            resolved_chat_id,
            message_id,
        )
        return message_id, resolved_chat_id

    except TelegramForbiddenError:
        logger.error(
            "Нет прав на публикацию в канал %s (пост %s)",
            chat_id,
            post.id,
        )
        raise
    except TelegramBadRequest as e:
        logger.error(
            "BadRequest при публикации поста %s: %s",
            post.id,
            e.message,
        )
        raise
    except Exception:
        logger.exception("Ошибка публикации поста %s", post.id)
        raise
