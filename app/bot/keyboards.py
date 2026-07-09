from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_sources_kb(sources) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in sources:
        builder.button(text=s.name, callback_data=f"source_{s.id}")
    builder.adjust(1)
    return builder.as_markup()

def get_specialties_kb(specialties) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sp in specialties:
        builder.button(text=sp.name, callback_data=f"specialty_{sp.id}")
    builder.button(text="Все специальности", callback_data="specialty_all")
    builder.adjust(1)
    return builder.as_markup()

def get_doctors_kb(doctors) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in doctors:
        builder.button(text=d.full_name, callback_data=f"doctor_{d.id}")
    builder.button(text="Все врачи", callback_data="doctor_all")
    builder.adjust(1)
    return builder.as_markup()

def get_filters_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Любое время (пропустить)", callback_data="filter_skip")
    return builder.as_markup()

def get_subscriptions_kb(subscriptions) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sub in subscriptions:
        if sub.doctor:
            desc = f"👨‍⚕️ {sub.doctor.full_name}"
        elif sub.specialty:
            desc = f"🩺 {sub.specialty.name}"
        else:
            desc = "Все врачи"
        builder.button(text=f"❌ {desc}", callback_data=f"delsub_{sub.id}")
    builder.adjust(1)
    return builder.as_markup()

def get_main_menu_kb() -> ReplyKeyboardMarkup:
    kb = [
        [
            KeyboardButton(text="🩺 Создать подписку"),
            KeyboardButton(text="📋 Мои подписки")
        ],
        [
            KeyboardButton(text="📅 Свободные талоны"),
            KeyboardButton(text="⚙️ Настройки")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_view_specialties_kb(specialties) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sp in specialties:
        builder.button(text=sp.name, callback_data=f"viewspec_{sp.id}")
    builder.adjust(1)
    return builder.as_markup()
