import asyncio
import json
import logging
from redis.asyncio import Redis
from aiogram import Bot
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Subscription, User, Ticket, Doctor, Specialty

logger = logging.getLogger(__name__)

async def start_notifier(bot: Bot):
    redis = Redis.from_url(settings.REDIS_URL)
    pubsub = redis.pubsub()
    await pubsub.subscribe("ticket_events")
    
    logger.info("Notifier started, listening to ticket_events")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await process_event(bot, data)
    except asyncio.CancelledError:
        logger.info("Notifier stopped")
    finally:
        await pubsub.unsubscribe("ticket_events")
        await redis.close()

async def process_event(bot: Bot, data: dict):
    # data example: {"ticket_id": 123, "status": "freed", "doctor_id": 1, "specialty_id": 2, "source_id": 1}
    status = data.get("status")
    if status not in ("freed", "new"):
        return
        
    doctor_id = data.get("doctor_id")
    specialty_id = data.get("specialty_id")
    source_id = data.get("source_id")
    ticket_id = data.get("ticket_id")

    async with AsyncSessionLocal() as session:
        # get ticket info for message
        result = await session.execute(
            select(Ticket, Doctor, Specialty)
            .join(Doctor)
            .join(Specialty)
            .where(Ticket.id == ticket_id)
        )
        row = result.first()
        if not row:
            return
        ticket, doctor, specialty = row
        
        # find matching subscriptions
        stmt = select(Subscription, User).join(User).where(
            Subscription.source_id == source_id,
            (Subscription.specialty_id == None) | (Subscription.specialty_id == specialty_id),
            (Subscription.doctor_id == None) | (Subscription.doctor_id == doctor_id)
        )
        
        subs_result = await session.execute(stmt)
        for sub, user in subs_result.all():
            msg = f"New ticket available!\nDoctor: {doctor.full_name}\nSpecialty: {specialty.name}\nDate: {ticket.date} {ticket.time}"
            try:
                await bot.send_message(user.telegram_id, msg)
            except Exception as e:
                logger.error(f"Failed to send message to {user.telegram_id}: {e}")
