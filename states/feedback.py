from aiogram.fsm.state import State, StatesGroup


class FeedbackStates(StatesGroup):
    waiting_review = State()
    waiting_support = State()
    support_done = State()
