# 🐶 PugBot v2.0

Telegram-бот для создания, планирования и публикации постов.

Первый публичный релиз.

## Возможности

- 📝 Создание постов (текст, медиа, кнопки, форматирование, теги)
- 📂 Черновики
- 📅 Очередь и отложенная публикация
- 📚 История публикаций
- 🗑 Управление опубликованными постами
- 📋 Шаблоны
- 📺 Несколько каналов
- 🌍 Часовые пояса
- ⏳ Автоудаление публикаций
- 👤 Управление администраторами проекта (только владелец)
- ⭐ Отзывы и 🛠 Поддержка
- 📊 Аналитика (Insights) — полная панель для владельца; для остальных — тизер о будущем обновлении

## Требования

- Python 3.11+
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))

## Установка

```bash
git clone <repo-url> PugBot
cd PugBot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Отредактируйте `.env`:

```env
BOT_TOKEN=123456:ABC...
ADMIN_GROUP_ID=-100...
OWNER_ID=587458401
OFFICIAL_CHANNEL_URL=https://t.me/PugBotOfficial
DEFAULT_TIMEZONE=Europe/Kyiv
```

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен бота (обязательно) |
| `OWNER_ID` | Telegram user id владельца (рекомендуется) |
| `ADMIN_GROUP_ID` | Группа для отзывов, поддержки и служебных уведомлений |
| `OFFICIAL_CHANNEL_URL` | Ссылка на официальный канал |
| `DEFAULT_TIMEZONE` | IANA-пояс по умолчанию |
| `CHANNEL_ID` | Опциональный fallback-канал |

`OWNER_ID` нельзя удалить из списка администраторов. Без `OWNER_ID` бот запускается, но полная аналитика недоступна (в лог пишется предупреждение).

## Запуск

```bash
python main.py
```

Подключите канал: добавьте бота администратором канала с правом **публикации сообщений**. Канал появится в ⚙️ Настройки → 📺 Каналы.

## Структура

```
config.py              # конфигурация из .env
main.py                # точка входа
handlers/              # роутеры UI
keyboards/             # клавиатуры
database/              # модели и репозитории (SQLite)
services/              # публикация, планировщик, Insights
middlewares.py         # контроль доступа
utils/                 # access, timezones, admin notify
assets/welcome.png     # приветственное изображение
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
