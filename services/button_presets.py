"""Пресеты кнопок.

Минимальная реализация через константы.
Позже можно перенести в таблицу button_presets без смены API.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ButtonPreset:
    key: str
    title: str
    default_url: str | None = None


DEFAULT_BUTTON_PRESETS: tuple[ButtonPreset, ...] = (
    ButtonPreset(key="youtube", title="📺 YouTube"),
    ButtonPreset(key="telegram", title="💬 Telegram"),
    ButtonPreset(key="site", title="🌐 Сайт"),
    ButtonPreset(key="buy", title="📦 Купить"),
)


def get_preset(key: str) -> ButtonPreset | None:
    for preset in DEFAULT_BUTTON_PRESETS:
        if preset.key == key:
            return preset
    return None


def list_presets() -> tuple[ButtonPreset, ...]:
    return DEFAULT_BUTTON_PRESETS
