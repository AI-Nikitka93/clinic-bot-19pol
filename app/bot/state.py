from aiogram.fsm.state import State, StatesGroup

class SubscriptionFlow(StatesGroup):
    selecting_source = State()
    selecting_specialty = State()
    selecting_doctor = State()
    selecting_filters = State()
