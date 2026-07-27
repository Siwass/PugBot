# Аудит безопасности доступа к каналам

## Проблема
Часть кода резолвила канал **глобально** (первый в БД / channel_id без ownership):
- `get_publish_chat_id()` / `get_active_channel()` / `get_channel_chat_id(id)`
- `update_channel(post_id, channel_id)` из callback без проверки владельца
- публикация могла уйти в чужой канал при подставленном channel_id

## Решение
Центральный модуль `services/channel_access.py`:
- ownership через `channel_admins` (БД)
- живая проверка через Telegram API (`get_chat_member`): пользователь — админ, бот в канале
- `resolve_publish_chat_id(user_id, channel_id=...)` — только свои каналы

## Закрытые точки
| Место | Защита |
|-------|--------|
| `services/publishing.py` | ownership + live verify перед отправкой |
| `services/channel_resolver.py` | user-scoped API; глобальный get_default убран из publish-path |
| `confirm_publish` / `edit` / `schedule_wizard` | `user_owns_channel_id` перед `update_channel` |
| `drafts` / `published` | chat_id только для автора |
| `create` / `templates` | default_channel только если owned |
| `settings` default + admins | ownership + live verify |
| `publish` / `queue` | author_id + publish_post ownership |

## Правило
Ни один `channel_id` из callback/БД не принимается без проверки:
`channel_admins.user_id == current_user` (+ live TG при публикации и admin-ops).
