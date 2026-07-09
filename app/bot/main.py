import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from app.core.config import settings
from app.bot.handlers import base, subscription

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

dp.include_router(base.router)
dp.include_router(subscription.router)

async def set_webhook():
    if settings.WEBHOOK_URL:
        # Assuming WEBHOOK_URL is the base URL like https://myapp.vercel.app
        url = f"{settings.WEBHOOK_URL.rstrip('/')}/api/webhook"
        await bot.set_webhook(url)
        logger.info(f"Webhook set to {url}")

