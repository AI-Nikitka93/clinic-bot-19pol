import asyncio
import logging
import os
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.models import User, Source, Specialty, Doctor, Ticket, Subscription
from app.scraper.parser import scrape_all_tickets
from app.scraper.differ import process_diff_and_notify
from aiogram import Bot

from app.core.config import settings

logger = logging.getLogger(__name__)

async def run_scraper_job():
    logger.info("Starting scraper job...")
    redis_url = settings.REDIS_URL
    redis_client = redis.from_url(redis_url, decode_responses=True)
    
    bot_token = settings.BOT_TOKEN
    bot = Bot(token=bot_token) if bot_token else None
    
    try:
        new_state = await scrape_all_tickets()
        logger.info("Scraping finished. Syncing with PostgreSQL...")
        
        async with AsyncSessionLocal() as session:
            # 1. Sync Source
            result = await session.execute(select(Source).where(Source.name == "19-я поликлиника"))
            source = result.scalar_one_or_none()
            if not source:
                source = Source(name="19-я поликлиника", base_url="http://self.19crp.by:8028/ticket/")
                session.add(source)
                await session.commit()
                await session.refresh(source)
            
            # 2. Cache Specialties
            result = await session.execute(select(Specialty).where(Specialty.source_id == source.id))
            specialties = {s.external_id: s for s in result.scalars().all()}
            
            # 3. Cache Doctors
            result = await session.execute(select(Doctor))
            doctors = {d.external_id: d for d in result.scalars().all()}
            
            # 4. Get active tickets in DB
            result = await session.execute(select(Ticket.id).where(Ticket.status == "available"))
            active_ticket_ids = set(row[0] for row in result.all())
            
            # Process specialties and doctors
            for spec_name, spec_data in new_state.items():
                spec_ext_id = spec_data["id"]
                if spec_ext_id not in specialties:
                    spec = Specialty(source_id=source.id, external_id=spec_ext_id, name=spec_name)
                    session.add(spec)
                    await session.commit()
                    await session.refresh(spec)
                    specialties[spec_ext_id] = spec
                
                for doc_name, doc_data in spec_data["doctors"].items():
                    doc_ext_id = doc_data["id"]
                    if doc_ext_id not in doctors:
                        doc = Doctor(specialty_id=specialties[spec_ext_id].id, external_id=doc_ext_id, full_name=doc_name)
                        session.add(doc)
                        await session.commit()
                        await session.refresh(doc)
                        doctors[doc_ext_id] = doc

            # Create helper mapping for doctor database IDs
            doctors_by_id = {d.id: d for d in doctors.values()}

            # Collect parsed tickets
            parsed_tickets_map = {}
            for spec_name, spec_data in new_state.items():
                for doc_name, doc_data in spec_data["doctors"].items():
                    doc_ext_id = doc_data["id"]
                    for t_id, t_datetime_str in doc_data["tickets"].items():
                        parsed_tickets_map[int(t_id)] = {
                            "doc_id": doctors[doc_ext_id].id,
                            "datetime_str": t_datetime_str
                        }
            
            parsed_ticket_ids = set(parsed_tickets_map.keys())
            
            # 5. Booked tickets (disappeared from site)
            booked_ids = active_ticket_ids - parsed_ticket_ids
            if booked_ids:
                logger.info(f"Booking {len(booked_ids)} tickets...")
                # SQLAlchemy in_ list limit check - typically 1000 items is fine, but we chunk it just in case
                booked_list = list(booked_ids)
                chunk_size = 500
                for i in range(0, len(booked_list), chunk_size):
                    chunk = booked_list[i:i + chunk_size]
                    await session.execute(
                        update(Ticket)
                        .where(Ticket.id.in_(chunk))
                        .values(status="booked", last_seen_at=datetime.utcnow())
                    )
                await session.commit()
            
            # 6. New tickets (appeared on site)
            new_ids = parsed_ticket_ids - active_ticket_ids
            new_tickets_to_notify = []
            
            if new_ids:
                logger.info(f"Found {len(new_ids)} new tickets. Updating status...")
                # Query existing tickets in database in chunks
                new_list = list(new_ids)
                existing_tickets = {}
                chunk_size = 500
                for i in range(0, len(new_list), chunk_size):
                    chunk = new_list[i:i + chunk_size]
                    res = await session.execute(select(Ticket).where(Ticket.id.in_(chunk)))
                    for t in res.scalars().all():
                        existing_tickets[t.id] = t
                
                for t_id in new_ids:
                    t_info = parsed_tickets_map[t_id]
                    dt_parts = t_info["datetime_str"].split(" ")
                    t_date = datetime.strptime(dt_parts[0], "%Y-%m-%d").date()
                    t_time = datetime.strptime(dt_parts[1], "%H:%M").time()
                    
                    if t_id in existing_tickets:
                        ticket = existing_tickets[t_id]
                        ticket.status = "available"
                        ticket.last_seen_at = datetime.utcnow()
                    else:
                        ticket = Ticket(
                            id=t_id,
                            doctor_id=t_info["doc_id"],
                            date=t_date,
                            time=t_time,
                            status="available"
                        )
                        session.add(ticket)
                    
                    new_tickets_to_notify.append({
                        "id": t_id,
                        "doctor_id": t_info["doc_id"],
                        "specialty_id": doctors_by_id[t_info["doc_id"]].specialty_id,
                        "date": t_date,
                        "time": t_time
                    })
                
                await session.commit()
            
            # 7. Notify subscribers
            if bot and new_tickets_to_notify:
                logger.info(f"Notifying subscribers about {len(new_tickets_to_notify)} new tickets...")
                for nt in new_tickets_to_notify:
                    # Find doctor and specialty names
                    result = await session.execute(
                        select(Doctor, Specialty)
                        .join(Specialty)
                        .where(Doctor.id == nt["doctor_id"])
                    )
                    row = result.first()
                    if not row:
                        continue
                    doctor, specialty = row
                    
                    # Find matching subscriptions
                    stmt = select(Subscription, User).join(User).where(
                        Subscription.source_id == source.id,
                        (Subscription.specialty_id == None) | (Subscription.specialty_id == specialty.id),
                        (Subscription.doctor_id == None) | (Subscription.doctor_id == doctor.id)
                    )
                    
                    subs_result = await session.execute(stmt)
                    for sub, user in subs_result.all():
                        msg = (
                            f"🔔 Новый свободный талон!\n"
                            f"👨‍⚕️ Врач: {doctor.full_name}\n"
                            f"🩺 Специальность: {specialty.name}\n"
                            f"📅 Дата: {nt['date'].strftime('%d.%m.%Y')} в {nt['time'].strftime('%H:%M')}\n"
                            f"🔗 Записаться: http://self.19crp.by:8028/ticket/"
                        )
                        try:
                            await bot.send_message(user.telegram_id, msg)
                            logger.info(f"Notification sent to user {user.telegram_id} for doctor {doctor.full_name}")
                        except Exception as send_err:
                            logger.error(f"Failed to send notification to {user.telegram_id}: {send_err}")

        # Process diff and update state in Redis for backward compatibility
        logger.info("Processing Redis state...")
        await process_diff_and_notify(redis_client, new_state)
        logger.info("Scraper job finished successfully!")
        
    except Exception as e:
        logger.error(f"Error in scraper job: {e}")
        raise e
    finally:
        await redis_client.aclose()
        if bot:
            await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if sys.platform == 'win32':
        import selectors
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_scraper_job())
        finally:
            loop.close()
    else:
        asyncio.run(run_scraper_job())
