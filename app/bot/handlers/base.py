from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
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
            select(Ticket, Doctor, Specialty)
            .join(Doctor, Ticket.doctor_id == Doctor.id)
            .join(Specialty, Doctor.specialty_id == Specialty.id)
            .where(Ticket.status == "available")
            .order_by(Specialty.name, Doctor.full_name, Ticket.date, Ticket.time)
            .limit(100)
        )
        rows = result.all()
        if not rows:
            await message.answer("Свободных талонов в данный момент нет. Попробуйте проверить позже.", reply_markup=get_main_menu_kb())
            return
            
        by_spec = {}
        for ticket, doctor, specialty in rows:
            if specialty.name not in by_spec:
                by_spec[specialty.name] = {}
            if doctor.full_name not in by_spec[specialty.name]:
                by_spec[specialty.name][doctor.full_name] = []
            by_spec[specialty.name][doctor.full_name].append(f"{ticket.date.strftime('%d.%m')} в {ticket.time.strftime('%H:%M')}")
            
        text = "📅 **Актуальные свободные талоны:**\n\n"
        for spec_name, docs_dict in by_spec.items():
            text += f"🩺 **{spec_name}**:\n"
            for doc_name, slots in docs_dict.items():
                text += f"  👨‍⚕️ {doc_name}:\n"
                text += f"     Талоны: {', '.join(slots[:6])}\n"
            text += "\n"
            
        text += "🔗 Записаться на сайте: http://self.19crp.by:8028/ticket/"
        await message.answer(text, reply_markup=get_main_menu_kb())
