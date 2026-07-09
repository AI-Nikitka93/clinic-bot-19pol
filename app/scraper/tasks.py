import asyncio
import logging
import os
import redis.asyncio as redis
from app.scraper.parser import scrape_all_tickets
from app.scraper.differ import process_diff_and_notify

logger = logging.getLogger(__name__)

async def run_scraper_job():
    logger.info("Starting scraper job...")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    # Upstash Redis might require rediss:// for TLS, from_url handles it nicely.
    redis_client = redis.from_url(redis_url, decode_responses=True)
    
    try:
        new_state = await scrape_all_tickets()
        logger.info("Scraping finished. Processing diff...")
        await process_diff_and_notify(redis_client, new_state)
    except Exception as e:
        logger.error(f"Error in scraper job: {e}")
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scraper_job())
