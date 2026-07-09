import asyncio
import logging
import sys
from app.scraper.tasks import run_scraper_job

logger = logging.getLogger(__name__)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("Starting scraper daemon loop...")
    while True:
        try:
            logger.info("Triggering scraper job...")
            await run_scraper_job()
        except Exception as e:
            logger.error(f"Error in scraper loop iteration: {e}")
        
        # Interval is 2 minutes (120 seconds) to satisfy rate limits and react fast
        logger.info("Sleeping for 120 seconds before next run...")
        await asyncio.sleep(120)

if __name__ == "__main__":
    if sys.platform == 'win32':
        import selectors
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        finally:
            loop.close()
    else:
        asyncio.run(main())
