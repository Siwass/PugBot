# PugBot v2.0 — merge notes

## Strategy
- Base: CyberTrip Publisher v3.0 (today’s UX: drafts, queue, formatting, preview, publish)
- Kept from PugBot: reviews, support, branding, welcome image, admin group, channel connect flow
- New in v2.0: timezones, auto-delete, cleaner logging

## Files only from CyberTrip (carried as-is)
- handlers/post/* (drafts, queue, queue_actions, formatting, preview_service, edit, …)
- keyboards/draft_preview.py, formatting.py (CT structure), queue_preview.py
- services/publishing.py (caption limit / split)

## Files only from PugBot (kept)
- handlers/feedback.py, handlers/diagnostics.py
- states/feedback.py
- utils/admin_notify.py, debug_report.py, last_error.py
- assets/welcome.png
- handlers/channels.py (human owner resolution)
- keyboards/menu.py (Отзывы / Поддержка / official channel)

## Merged
- config.py — PugBot branding + ADMIN_GROUP_ID + OFFICIAL_CHANNEL_URL + DEFAULT_TIMEZONE, version 2.0
- main.py — PB routers (feedback, channels first) + no noisy DEBUG middleware
- database/db.py — PB purge legacy + new columns
- database/models.py — timezone, auto_delete fields
- database/user_settings_repository.py — set_timezone, set_default_auto_delete
- database/post_repository.py — set_auto_delete, claim_due_auto_deletes
- services/scheduled_publisher.py — admin notify + auto-delete worker
- handlers/settings.py — timezone + auto-delete UI
- handlers/about.py, handlers/start.py — v2 feature list
- handlers/post/create.py, templates.py, publish.py — apply default auto-delete

## New features
1. 🌍 Timezones — Settings → Часовой пояс (IANA list)
2. ⏳ Auto-delete — Settings default 24/48/72/96h; applied on publish; background deletion
3. ✏️ One-click text edit — from CT drafts/queue edit flows
4. 📋 Full queue editing — CT queue_actions
5. 💬 Simpler admin texts — reduced emoji noise in logs
6. 📄 Logging — INFO default, aiogram/sqlalchemy DEBUG suppressed

## Env
```
BOT_TOKEN=...
ADMIN_GROUP_ID=-100...
OFFICIAL_CHANNEL_URL=https://t.me/PugBotOfficial
DEFAULT_TIMEZONE=Europe/Kyiv
```
