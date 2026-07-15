import asyncio
import logging
import os
import time
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.models import User, Source, Specialty, Doctor, Ticket, Subscription
from app.scraper.parser import scrape_all_tickets
from aiogram import Bot

from app.core.config import settings

logger = logging.getLogger(__name__)

async def run_single_scrape():
    logger.info("Starting single scrape iteration...")
    redis_url = settings.REDIS_URL
    redis_client = None
    if redis_url:
        try:
            redis_client = redis.from_url(redis_url, decode_responses=True)
            await redis_client.ping()
        except Exception as re_err:
            logger.warning(f"Redis connection failed: {re_err}. Proceeding without Redis.")
            redis_client = None
            
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
            successfully_scraped_doctor_ids = set()
            for spec_name, spec_data in new_state.items():
                for doc_name, doc_data in spec_data["doctors"].items():
                    doc_ext_id = doc_data["id"]
                    doc_internal_id = doctors[doc_ext_id].id
                    successfully_scraped_doctor_ids.add(doc_internal_id)
                    for t_id, t_datetime_str in doc_data["tickets"].items():
                        parsed_tickets_map[int(t_id)] = {
                            "doc_id": doc_internal_id,
                            "datetime_str": t_datetime_str
                        }
            
            if not successfully_scraped_doctor_ids:
                logger.warning("No doctors were scraped successfully. Skipping sync.")
                return

            parsed_ticket_ids = set(parsed_tickets_map.keys())
            
            # 4. Get active tickets in DB
            result = await session.execute(
                select(Ticket.id)
                .where(Ticket.status == "available")
                .where(Ticket.doctor_id.in_(list(successfully_scraped_doctor_ids)))
            )
            active_ticket_ids = set(row[0] for row in result.all())
            
            # 5. Booked tickets (disappeared from site)
            booked_ids = active_ticket_ids - parsed_ticket_ids
            if booked_ids:
                logger.info(f"Booking {len(booked_ids)} tickets...")
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
                
                # Pre-fetch all doctors and specialties mapping for fast lookup
                # (We already have doctors_by_id and specialties dictionary)
                
                for nt in new_tickets_to_notify:
                    doc = doctors_by_id.get(nt["doctor_id"])
                    if not doc: continue
                    
                    # Find specialty
                    spec = None
                    for s in specialties.values():
                        if s.id == doc.specialty_id:
                            spec = s
                            break
                    if not spec: continue
                    
                    stmt = select(Subscription, User).join(User).where(
                        Subscription.source_id == source.id,
                        (Subscription.specialty_id.is_(None)) | (Subscription.specialty_id == spec.id),
                        (Subscription.doctor_id.is_(None)) | (Subscription.doctor_id == doc.id)
                    )
                    
                    subs_result = await session.execute(stmt)
                    subscribers = subs_result.all()
                    
                    if not subscribers:
                        continue
                        
                    msg = (
                        f"🔔 Новый свободный талон!\n"
                        f"👨‍⚕️ Врач: {doc.full_name}\n"
                        f"🩺 Специальность: {spec.name}\n"
                        f"📅 Дата: {nt['date'].strftime('%d.%m.%Y')} в {nt['time'].strftime('%H:%M')}\n"
                        f"🔗 Записаться: http://self.19crp.by:8028/ticket/"
                    )
                    
                    for sub, user in subscribers:
                        try:
                            await bot.send_message(user.telegram_id, msg)
                            logger.info(f"Notification sent to user {user.telegram_id} for doctor {doc.full_name}")
                            await asyncio.sleep(0.05) # Prevent Telegram 429 Too Many Requests
                        except Exception as send_err:
                            logger.error(f"Failed to send notification to {user.telegram_id}: {send_err}")

        logger.info("Single scrape iteration finished successfully.")
        
    except Exception as e:
        logger.error(f"Error in single scrape iteration: {e}")
        raise e
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception as close_err:
                logger.debug(f"Redis close error: {close_err}")
        if bot:
            await bot.session.close()

async def run_scraper_job():
    logger.info("Starting scraper loop task...")
    redis_url = settings.REDIS_URL
    redis_client = None
    if redis_url:
        try:
            redis_client = redis.from_url(redis_url, decode_responses=True)
            await redis_client.ping()
        except Exception as re_err:
            logger.warning(f"Redis connection failed: {re_err}")
            redis_client = None

    lock_key = "scraper_running_lock"
    if redis_client:
        acquired = await redis_client.set(lock_key, "1", ex=280, nx=True)
        if not acquired:
            logger.info("Another scraper instance is actively running. Exiting.")
            await redis_client.aclose()
            return
            
    try:
        start_time = time.time()
        iteration = 0
        while time.time() - start_time < 270:
            if iteration > 0:
                logger.info("Waiting 120 seconds for the next scrape iteration...")
                await asyncio.sleep(120)
                
            logger.info(f"--- Scraper Iteration {iteration + 1} ---")
            if redis_client:
                await redis_client.expire(lock_key, 280)
                
            try:
                await run_single_scrape()
            except Exception as e:
                logger.error(f"Error in iteration {iteration + 1}: {e}")
                
            iteration += 1
            
    finally:
        if redis_client:
            try:
                await redis_client.delete(lock_key)
                await redis_client.aclose()
            except Exception as close_err:
                logger.debug(f"Redis cleanup error: {close_err}")
        logger.info("Scraper loop task finished.")

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
