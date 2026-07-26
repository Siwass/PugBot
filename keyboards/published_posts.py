from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Сегодня",
                    callback_data="pub_period:today",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Вчера",
                    callback_data="pub_period:yesterday",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 За неделю",
                    callback_data="pub_period:week",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="pub_back_menu",
                )
            ],
        ]
    )


def posts_list_keyboard(posts: list, period: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for post in posts:
        label = _list_label(post)
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"pub_open:{post.id}:{period}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К периодам",
                callback_data="pub_periods",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_actions_keyboard(post_id: int, period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Дублировать",
                    callback_data=f"dup_post:{post_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"pub_delete:{post_id}:{period}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"pub_period:{period}",
                )
            ],
        ]
    )


def confirm_delete_keyboard(post_id: int, period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=f"pub_delete_yes:{post_id}:{period}",
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"pub_open:{post_id}:{period}",
                ),
            ]
        ]
    )


def after_delete_keyboard(period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ К списку",
                    callback_data=f"pub_period:{period}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="pub_back_menu",
                )
            ],
        ]
    )


def _list_label(post) -> str:
    time_str = "??:??"
    if post.published_at is not None:
        time_str = post.published_at.strftime("%H:%M")

    title = _post_title(post)
    return f"{time_str} • {title}"


def _post_title(post) -> str:
    if post.text:
        # Убираем простые HTML-теги для отображения в кнопке
        title = post.text
        for tag in ("<b>", "</b>", "<i>", "</i>", "<u>", "</u>", "<s>", "</s>"):
            title = title.replace(tag, "")
        # Ссылки вида <a href="...">text</a> — оставляем только text упрощённо
        while "<a " in title and "</a>" in title:
            start = title.find("<a ")
            mid = title.find(">", start)
            end = title.find("</a>", mid)
            if start == -1 or mid == -1 or end == -1:
                break
            title = title[:start] + title[mid + 1 : end] + title[end + 4 :]
        title = title.replace("\n", " ").strip()
        if len(title) > 32:
            title = title[:32] + "…"
        return title or "Пост без текста"
    if post.media:
        return "📷 Медиа"
    return "Пост без текста"
