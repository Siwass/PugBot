# Администраторы: UX-полировка + финальный аудит безопасности

## UX
- Хаб: «📺 Канал» + описание раздела
- Добавление: дружелюбный текст, ID / пересылка / @username
- Успех add/remove — коммерческие формулировки
- «Некого удалять» — понятное сообщение
- Бот не админ / пользователь потерял права — отдельные тексты
- Служебные логи promote/demote (by, target, chat, time)

## Аудит безопасности (канал)

Проверено ~40+ точек (handlers/post/*, settings, services, scheduler).

### Уже через channel_access / ownership
- publishing.publish_post (ownership + live TG)
- confirm_publish / edit / schedule_wizard (channel select)
- drafts / published delete (author + resolve_chat_id_for_user)
- create / templates default_channel
- settings default + admins (live verify на каждой операции)
- queue / publish / retry (author_id + publish_post)

### Исправлено в этом проходе
- published: title канала только через get_owned_channel
- admin list/add/remove/del: live verify_channel_access
- тексты bot_missing / not_tg_admin

### Намеренно без channel_access (не publish path)
- channels.py — подключение канала (my_chat_member)
- feedback — сводка своих каналов get_channels_for_user
- insights — агрегаты OWNER
- get_all_channels — только системно

### Callback / post_id
Все post-операции: `post.author_id == from_user.id` до действия.
channel_id из callback: `user_owns_channel_id` до update_channel.

### Scheduler
publish_due_posts → publish_post(author ownership + live TG).
Автоудаление — только telegram_chat_id, сохранённый при публикации
своего поста (подставить чужой channel_id при schedule нельзя).

## Итог
Система доступа к каналам централизована.
Прямых publish/admin путей в обход ownership + Telegram API не осталось.
