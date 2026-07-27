# PugBot v2.0 — публичный доступ

## Цель
Открыть бот для всех пользователей Telegram без ручного добавления в `bot_admins`.

## Модель ролей

| Роль | Кто | Права |
|------|-----|--------|
| Пользователь | любой Telegram user | все пользовательские функции |
| Служебный админ | запись в `bot_admins` | резерв под будущие admin-функции |
| Владелец | `OWNER_ID` / `is_owner` | Insights + управление `bot_admins` |

## Изменённые файлы
- `utils/access.py` — `user_has_access` всегда True; добавлены `is_project_owner`, `is_owner_id`
- `middlewares.py` — публичный доступ, текст отказа обновлён под будущий ban-list
- `handlers/settings.py` — кнопка «Администраторы» только OWNER; все admin-хендлеры с guard
- `handlers/insights.py` — использует общий `is_project_owner` (логика без изменений)
- `database/models.py` — docstring `BotAdmin`
- `handlers/start.py`, `handlers/about.py` — список возможностей без «управления админами»
- `README.md` — описание публичного доступа

## Не менялось
Очередь, публикация, шаблоны, история, каналы, часовые пояса, автоудаление,
отзывы, поддержка, Insights (owner / teaser).
