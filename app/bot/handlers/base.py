from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.models import User

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
    await message.answer("Welcome to Clinic Ticket Monitoring Bot!\nUse /help to see available commands.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Available commands:\n/start - Start the bot\n/help - Help message\n/subscribe - Add a new subscription\n/subscriptions - List active subscriptions\n/settings - Bot settings")

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    await message.answer("Settings menu is not implemented yet.")
