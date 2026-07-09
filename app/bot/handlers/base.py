from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.models import User, Ticket, Doctor, Specialty
from app.bot.keyboards import get_main_menu_kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username
            )
            session.add(user)
            await session.commit()
    await message.answer(
        "👋 Добро пожаловать в бот мониторинга талонов 19-й поликлиники!\n\n"
        "С помощью этого бота вы можете подписаться на появление свободных талонов к нужным врачам, "
        "а также просматривать актуальное расписание.",
        reply_markup=get_main_menu_kb()
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Используйте кнопки меню внизу для управления ботом:\n"
        "🩺 Создать подписку — подписаться на появление талонов\n"
        "📋 Мои подписки — посмотреть/удалить ваши подписки\n"
        "📅 Свободные талоны — показать список доступных талонов прямо сейчас\n"
        "⚙️ Настройки — настройки уведомлений",
        reply_markup=get_main_menu_kb()
    )

@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: types.Message):
    await message.answer("Раздел настроек находится в разработке.", reply_markup=get_main_menu_kb())

@router.message(F.text == "🩺 Создать подписку")
async def menu_subscribe(message: types.Message, state: FSMContext):
    from app.bot.handlers.subscription import cmd_subscribe
    await cmd_subscribe(message, state)

@router.message(F.text == "📋 Мои подписки")
async def menu_subscriptions(message: types.Message):
    from app.bot.handlers.subscription import list_subscriptions
    await list_subscriptions(message)

@router.message(F.text == "📅 Свободные талоны")
async def menu_tickets(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Specialty)
            .join(Doctor)
            .join(Ticket)
            .where(Ticket.status == "available")
            .distinct()
            .order_by(Specialty.name)
        )
        specialties = result.scalars().all()
        if not specialties:
            await message.answer("Свободных талонов в данный момент нет. Попробуйте проверить позже.", reply_markup=get_main_menu_kb())
            return
            
        from app.bot.keyboards import get_view_specialties_kb
        await message.answer("Выберите направление для просмотра талонов:", reply_markup=get_view_specialties_kb(specialties))

@router.callback_query(F.data.startswith("viewspec_"))
async def process_view_specialty(callback: types.CallbackQuery):
    if callback.data == "viewspec_back":
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Specialty)
                .join(Doctor)
                .join(Ticket)
                .where(Ticket.status == "available")
                .distinct()
                .order_by(Specialty.name)
            )
            specialties = result.scalars().all()
            if not specialties:
                await callback.message.edit_text("Свободных талонов в данный момент нет.")
                return
                
            from app.bot.keyboards import get_view_specialties_kb
            await callback.message.edit_text("Выберите направление для просмотра талонов:", reply_markup=get_view_specialties_kb(specialties))
        return

    spec_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        spec_res = await session.execute(select(Specialty).where(Specialty.id == spec_id))
        specialty = spec_res.scalar_one_or_none()
        if not specialty:
            await callback.answer("Направление не найдено.")
            return
            
        result = await session.execute(
            select(Ticket, Doctor)
            .join(Doctor, Ticket.doctor_id == Doctor.id)
            .where(Doctor.specialty_id == spec_id, Ticket.status == "available")
            .order_by(Doctor.full_name, Ticket.date, Ticket.time)
        )
        rows = result.all()
        if not rows:
            await callback.message.edit_text(f"Свободных талонов по направлению «{specialty.name}» уже нет.")
            return
            
        by_doc = {}
        for ticket, doctor in rows:
            if doctor.full_name not in by_doc:
                by_doc[doctor.full_name] = []
            by_doc[doctor.full_name].append(f"{ticket.date.strftime('%d.%m')} в {ticket.time.strftime('%H:%M')}")
            
        text = f"🩺 **Свободные талоны: {specialty.name}**\n\n"
        
        # Limit to 8 doctors to prevent Telegram MESSAGE_TOO_LONG error
        doc_names = list(by_doc.keys())
        visible_docs = doc_names[:8]
        
        for doc_name in visible_docs:
            slots = by_doc[doc_name]
            text += f"👨‍⚕️ {doc_name}:\n"
            text += f"   Талоны: {', '.join(slots[:5])}\n"
            if len(slots) > 5:
                text += f"   (и еще {len(slots) - 5} талонов)\n"
            text += "\n"
            
        if len(doc_names) > 8:
            text += f"ℹ️ Показано 8 врачей из {len(doc_names)}. Полный список доступен при записи.\n\n"
            
        text += "🔗 Записаться на сайте: http://self.19crp.by:8028/ticket/"
        
        # Build clean keyboard with only "Back" button to reduce message payload size
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 К выбору направлений", callback_data="viewspec_back")
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
