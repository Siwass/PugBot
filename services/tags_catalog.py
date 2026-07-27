"""Централизованный каталог тегов.

Позже можно заменить на БД без смены API:
  list_categories(), get_category(key), normalize_tag()
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TagCategory:
    key: str
    title: str
    base_tags: tuple[str, ...]
    extra_tags: tuple[tuple[str, str], ...]  # (label, tag_without_hash)


TAG_CATEGORIES: tuple[TagCategory, ...] = (
    TagCategory(
        key="smartphones",
        title="📱 Смартфоны",
        base_tags=("#смартфоны", "#обзор", "#технологии"),
        extra_tags=(
            ("🍎 Apple", "apple"),
            ("📱 Samsung", "samsung"),
            ("🟠 Xiaomi", "xiaomi"),
            ("🟡 POCO", "poco"),
            ("🔵 HONOR", "honor"),
            ("🟢 realme", "realme"),
            ("⚫ OnePlus", "oneplus"),
            ("🟣 Google Pixel", "googlepixel"),
        ),
    ),
    TagCategory(
        key="laptops",
        title="💻 Ноутбуки",
        base_tags=("#ноутбуки", "#обзор", "#технологии"),
        extra_tags=(
            ("🍎 MacBook", "macbook"),
            ("💻 ASUS", "asus"),
            ("💻 Lenovo", "lenovo"),
            ("💻 HP", "hp"),
            ("💻 Acer", "acer"),
            ("💻 MSI", "msi"),
        ),
    ),
    TagCategory(
        key="photo",
        title="📷 Фото и видео",
        base_tags=("#фото", "#видео", "#техника"),
        extra_tags=(
            ("📷 Canon", "canon"),
            ("📷 Sony", "sony"),
            ("📷 Nikon", "nikon"),
            ("🎬 GoPro", "gopro"),
        ),
    ),
    TagCategory(
        key="games",
        title="🎮 Игры",
        base_tags=("#игры", "#гейминг", "#обзор"),
        extra_tags=(
            ("🎮 PlayStation", "playstation"),
            ("🟢 Xbox", "xbox"),
            ("🔴 Nintendo", "nintendo"),
            ("🖥 PC", "pcgaming"),
        ),
    ),
    TagCategory(
        key="ai",
        title="🤖 Искусственный интеллект",
        base_tags=("#ai", "#нейросети", "#технологии"),
        extra_tags=(
            ("🤖 ChatGPT", "chatgpt"),
            ("🔵 Claude", "claude"),
            ("🟢 Gemini", "gemini"),
            ("🟣 Midjourney", "midjourney"),
        ),
    ),
    TagCategory(
        key="gadgets",
        title="🔋 Гаджеты",
        base_tags=("#гаджеты", "#технологии", "#обзор"),
        extra_tags=(
            ("🔋 Powerbank", "powerbank"),
            ("🔌 Зарядки", "зарядки"),
            ("📦 Аксессуары", "аксессуары"),
        ),
    ),
    TagCategory(
        key="headphones",
        title="🎧 Наушники",
        base_tags=("#наушники", "#аудио", "#обзор"),
        extra_tags=(
            ("🎧 AirPods", "airpods"),
            ("🎧 Sony", "sony"),
            ("🎧 Samsung", "samsung"),
            ("🎧 Xiaomi", "xiaomi"),
        ),
    ),
    TagCategory(
        key="watches",
        title="⌚ Смарт-часы",
        base_tags=("#смартчасы", "#гаджеты", "#обзор"),
        extra_tags=(
            ("🍎 Apple Watch", "applewatch"),
            ("⌚ Samsung", "samsung"),
            ("⌚ Xiaomi", "xiaomi"),
            ("⌚ Huawei", "huawei"),
        ),
    ),
    TagCategory(
        key="tv",
        title="📺 Телевизоры",
        base_tags=("#телевизоры", "#обзор", "#технологии"),
        extra_tags=(
            ("📺 Samsung", "samsung"),
            ("📺 LG", "lg"),
            ("📺 Sony", "sony"),
            ("📺 Xiaomi", "xiaomi"),
        ),
    ),
    TagCategory(
        key="monitors",
        title="🖥 Мониторы",
        base_tags=("#мониторы", "#обзор", "#технологии"),
        extra_tags=(
            ("🖥 Samsung", "samsung"),
            ("🖥 LG", "lg"),
            ("🖥 Dell", "dell"),
            ("🖥 ASUS", "asus"),
        ),
    ),
    TagCategory(
        key="periphery",
        title="🖱 Периферия",
        base_tags=("#периферия", "#гаджеты", "#обзор"),
        extra_tags=(
            ("⌨️ Клавиатуры", "клавиатуры"),
            ("🖱 Мыши", "мыши"),
            ("🎙 Микрофоны", "микрофоны"),
        ),
    ),
    TagCategory(
        key="other",
        title="📦 Другое",
        base_tags=("#технологии", "#обзор"),
        extra_tags=(
            ("🔥 Хиты", "хиты"),
            ("🆕 Новинки", "новинки"),
            ("💡 Советы", "советы"),
        ),
    ),
)


def list_categories() -> tuple[TagCategory, ...]:
    return TAG_CATEGORIES


def get_category(key: str) -> TagCategory | None:
    for cat in TAG_CATEGORIES:
        if cat.key == key:
            return cat
    return None


def normalize_tag(raw: str) -> str:
    tag = (raw or "").strip()
    if not tag:
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    # убрать пробелы внутри
    tag = "#" + "".join(tag[1:].split())
    return tag.lower()


def merge_tags_into_text(text: str, tags: list[str]) -> str:
    """Добавляет теги в конец текста, без дублей."""
    body = (text or "").rstrip()
    existing = set()
    for part in body.replace("\n", " ").split():
        if part.startswith("#"):
            existing.add(part.lower())

    to_add = []
    for tag in tags:
        norm = normalize_tag(tag)
        if norm and norm not in existing and norm not in {t.lower() for t in to_add}:
            to_add.append(norm)

    if not to_add:
        return body

    block = " ".join(to_add)
    if body:
        return f"{body}\n\n{block}"
    return block
