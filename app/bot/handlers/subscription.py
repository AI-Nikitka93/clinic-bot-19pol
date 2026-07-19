from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.models import User, Source, Specialty, Doctor, Subscription
from app.bot.state import SubscriptionFlow
from app.bot.keyboards import get_sources_kb, get_specialties_kb, get_doctors_kb, get_filters_kb, get_subscriptions_kb

router = Router()

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source).where(Source.is_active))
        sources = result.scalars().all()
        if not sources:
            await message.answer("No sources available.")
            return
        if len(sources) == 1:
            source = sources[0]
            await state.update_data(source_id=source.id)
            result_spec = await session.execute(select(Specialty).where(Specialty.source_id == source.id))
            specialties = result_spec.scalars().all()
            await message.answer("Выберите специальность:", reply_markup=get_specialties_kb(specialties))
            await state.set_state(SubscriptionFlow.selecting_specialty)
        else:
            await message.answer("Выберите источник:", reply_markup=get_sources_kb(sources))
            await state.set_state(SubscriptionFlow.selecting_source)

@router.callback_query(SubscriptionFlow.selecting_source, F.data.startswith("source_"))
async def process_source(callback: types.CallbackQuery, state: FSMContext):
    source_id = int(callback.data.split("_")[1])
    await state.update_data(source_id=source_id)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Specialty).where(Specialty.source_id == source_id))
        specialties = result.scalars().all()
        await callback.message.edit_text("Выберите специальность:", reply_markup=get_specialties_kb(specialties))
        await state.set_state(SubscriptionFlow.selecting_specialty)

@router.callback_query(SubscriptionFlow.selecting_specialty, F.data.startswith("specialty_"))
async def process_specialty(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "specialty_all":
        await state.update_data(specialty_id=None, doctor_id=None)
        await callback.message.edit_text("Выберите фильтр времени:", reply_markup=get_filters_kb())
        await state.set_state(SubscriptionFlow.selecting_filters)
        return

    specialty_id = int(callback.data.split("_")[1])
    await state.update_data(specialty_id=specialty_id)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Doctor).where(Doctor.specialty_id == specialty_id))
        doctors = result.scalars().all()
        await callback.message.edit_text("Выберите врача:", reply_markup=get_doctors_kb(doctors))
        await state.set_state(SubscriptionFlow.selecting_doctor)

@router.callback_query(SubscriptionFlow.selecting_doctor, F.data.startswith("doctor_"))
async def process_doctor(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "doctor_all":
        await state.update_data(doctor_id=None)
    else:
        doctor_id = int(callback.data.split("_")[1])
        await state.update_data(doctor_id=doctor_id)
    
    await callback.message.edit_text("Выберите фильтр времени:", reply_markup=get_filters_kb())
    await state.set_state(SubscriptionFlow.selecting_filters)

@router.callback_query(SubscriptionFlow.selecting_filters, F.data.startswith("filter_"))
async def process_filters(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.message.answer("Пользователь не найден. Пожалуйста, перезапустите бота командой /start")
            await state.clear()
            return
        
        sub = Subscription(
            user_id=user.id,
            source_id=data.get("source_id"),
            specialty_id=data.get("specialty_id"),
            doctor_id=data.get("doctor_id")
        )
        session.add(sub)
        await session.commit()
    
    await callback.message.edit_text("✅ Подписка успешно сохранена! Вы получите уведомление, как только появятся новые свободные талоны.")
    await state.clear()

@router.message(Command("subscriptions"))
async def list_subscriptions(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription)
            .join(User)
            .where(User.telegram_id == message.from_user.id)
            .options(selectinload(Subscription.specialty), selectinload(Subscription.doctor))
        )
        subs = result.scalars().all()
        if not subs:
            await message.answer("У вас нет активных подписок.")
            return
        await message.answer("Ваши активные подписки (нажмите для удаления):", reply_markup=get_subscriptions_kb(subs))

@router.callback_query(F.data.startswith("delsub_"))
async def del_subscription(callback: types.CallbackQuery):
    sub_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if user:
            res = await session.execute(
                delete(Subscription).where(Subscription.id == sub_id, Subscription.user_id == user.id)
            )
            await session.commit()
            if res.rowcount > 0:
                await callback.answer("Подписка удалена")
                sub_res = await session.execute(
                    select(Subscription)
                    .where(Subscription.user_id == user.id)
                    .options(selectinload(Subscription.specialty), selectinload(Subscription.doctor))
                )
                subs = sub_res.scalars().all()
                if not subs:
                    await callback.message.edit_text("У вас больше нет активных подписок.")
                else:
                    await callback.message.edit_reply_markup(reply_markup=get_subscriptions_kb(subs))
                return
    await callback.answer("Ошибка: подписка не найдена или нет прав", show_alert=True)
