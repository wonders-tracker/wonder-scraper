#!/usr/bin/env python3
import asyncio
import logging

from app.core.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    logging.info("Starting dedicated scheduler worker...")
    start_scheduler()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logging.info("Scheduler worker shutting down.")


if __name__ == "__main__":
    asyncio.run(main())
