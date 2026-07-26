from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Тексты кнопок хаба (ReplyKeyboard)
HUB_FORMAT = "✨ Форматировать текст"
HUB_MEDIA = "📷 Добавить медиа"
HUB_BUTTONS = "🔗 Добавить кнопки"
HUB_PUBLISH = "🚀 Опубликовать сейчас"
HUB_SCHEDULE = "📅 Запланировать публикацию"
HUB_POST_SETTINGS = "📝 Настройки поста"
HUB_BACK = "⬅ Назад"

# Тексты кнопок инструментов форматирования
FMT_BOLD = "🅱 Жирный"
FMT_ITALIC = "📝 Курсив"
FMT_UNDERLINE = "📌 Подчеркнуть"
FMT_STRIKE = "❌ Зачеркнуть"
FMT_LINK = "🔗 Ссылка"
FMT_TAGS = "🏷 Теги"
FMT_DONE = "✅ Готово"
FMT_BACK = "⬅ Назад"

# Главный экран управления публикацией (ReplyKeyboard)
formatting_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=HUB_FORMAT)],
        [KeyboardButton(text=HUB_MEDIA)],
        [KeyboardButton(text=HUB_BUTTONS)],
        [KeyboardButton(text=HUB_POST_SETTINGS)],
        [KeyboardButton(text=HUB_PUBLISH)],
        [KeyboardButton(text=HUB_SCHEDULE)],
        [KeyboardButton(text=HUB_BACK)],
    ],
    resize_keyboard=True,
)

# Инструменты форматирования
format_tools_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=FMT_BOLD),
            KeyboardButton(text=FMT_ITALIC),
        ],
        [
            KeyboardButton(text=FMT_UNDERLINE),
            KeyboardButton(text=FMT_STRIKE),
        ],
        [
            KeyboardButton(text=FMT_LINK),
            KeyboardButton(text=FMT_TAGS),
        ],
        [
            KeyboardButton(text=FMT_DONE),
            KeyboardButton(text=FMT_BACK),
        ],
    ],
    resize_keyboard=True,
)
