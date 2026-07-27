from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
CHANNEL_ID: Optional[str] = os.getenv("CHANNEL_ID")

_admin_group_raw = os.getenv("ADMIN_GROUP_ID", "-1004318014570").strip()
try:
    ADMIN_GROUP_ID: int = int(_admin_group_raw)
except ValueError:
    ADMIN_GROUP_ID = -1004318014570

# Главный владелец PugBot (нельзя удалить из администраторов)
_owner_raw = (os.getenv("OWNER_ID") or "").strip()
try:
    OWNER_ID: Optional[int] = int(_owner_raw) if _owner_raw else None
except ValueError:
    OWNER_ID = None

OFFICIAL_CHANNEL_URL: str = os.getenv(
    "OFFICIAL_CHANNEL_URL",
    "https://t.me/PugBotOfficial",
).strip()

DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv").strip()

APP_NAME: str = "PugBot"
APP_VERSION: str = "2.0"
