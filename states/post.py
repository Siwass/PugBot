from aiogram.fsm.state import State, StatesGroup


class CreatePost(StatesGroup):

    # Создание поста
    waiting_text = State()

    # 🎨 Оформление текста
    formatting = State()
    waiting_format_text = State()

    waiting_link_text = State()
    waiting_link_url = State()

    # Медиа
    waiting_media = State()

    # Кнопки
    waiting_buttons = State()
    waiting_button_text = State()
    waiting_button_url = State()

    # Планирование
    waiting_schedule_choice = State()
    waiting_schedule = State()

    choosing_schedule_date = State()
    choosing_schedule_time = State()
    choosing_schedule_channel = State()

    # Предпросмотр
    preview = State()

    # Редактирование
    editing_text = State()
    editing_media = State()
    editing_buttons = State()

    # Создание своего шаблона
    waiting_template_name = State()
    waiting_template_text = State()

    # Теги
    waiting_custom_tag = State()

