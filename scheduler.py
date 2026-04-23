"""
Scheduler that fires the wildlife sighting summary every day at 9:00 PM IST.

Run as a long-lived process:
    python scheduler.py

Or use the provided cron entry (see README) for production deployments.

IST is UTC+5:30, so 9 PM IST = 15:30 UTC.
"""

import logging

import schedule
import time

from daily_summary import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 9 PM IST = 15:30 UTC
SCHEDULE_UTC = "15:30"


def job() -> None:
    try:
        run(dry_run=False)
    except Exception:
        logger.exception("Wildlife summary job failed.")


schedule.every().day.at(SCHEDULE_UTC).do(job)
logger.info("Scheduler started — wildlife summary will run daily at 9:00 PM IST (%s UTC).", SCHEDULE_UTC)

while True:
    schedule.run_pending()
    time.sleep(30)
