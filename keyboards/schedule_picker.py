from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SCHEDULE_TIME_SLOTS = (
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
    "22:00",
    "23:00",
)


def schedule_date_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟦 Сегодня",
                    callback_data="sch_pick_date:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟦 Завтра",
                    callback_data="sch_pick_date:1",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟦 Послезавтра",
                    callback_data="sch_pick_date:2",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📆 Другая дата",
                    callback_data="sch_pick_date:other",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="sch_wiz_cancel",
                )
            ],
        ]
    )


def schedule_time_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for index in range(0, len(SCHEDULE_TIME_SLOTS), 3):
        chunk = SCHEDULE_TIME_SLOTS[index : index + 3]
        rows.append(
            [
                InlineKeyboardButton(
                    text=slot,
                    callback_data=f"sch_pick_time:{slot.replace(':', '-')}",
                )
                for slot in chunk
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="✏️ Ввести вручную",
                callback_data="sch_pick_time:manual",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="sch_wiz_back",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
