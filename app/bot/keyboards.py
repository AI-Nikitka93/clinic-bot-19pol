from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
    builder.button(text="All Specialties", callback_data="specialty_all")
    builder.adjust(1)
    return builder.as_markup()

def get_doctors_kb(doctors) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in doctors:
        builder.button(text=d.full_name, callback_data=f"doctor_{d.id}")
    builder.button(text="All Doctors", callback_data="doctor_all")
    builder.adjust(1)
    return builder.as_markup()

def get_filters_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip (Any time)", callback_data="filter_skip")
    return builder.as_markup()

def get_subscriptions_kb(subscriptions) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sub in subscriptions:
        sub_desc = f"Sub {sub.id}: Src {sub.source_id}"
        if sub.specialty_id: sub_desc += f", Spec {sub.specialty_id}"
        if sub.doctor_id: sub_desc += f", Doc {sub.doctor_id}"
        builder.button(text=f"Delete {sub_desc}", callback_data=f"delsub_{sub.id}")
    builder.adjust(1)
    return builder.as_markup()
