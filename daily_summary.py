"""
Main orchestration script.
Run directly for a one-shot execution, or via scheduler.py for the daily 9 PM job.

Usage:
    python daily_summary.py          # run now
    python daily_summary.py --dry-run  # print summary, don't WhatsApp
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from instagram_fetcher import InstagramFetcher
from wildlife_analyzer import WildlifeAnalyzer
from whatsapp_sender import WhatsAppSender

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        logger.error("Missing required environment variable: %s", key)
        sys.exit(1)
    return val


def run(dry_run: bool = False) -> None:
    logger.info("=== Wildlife Sighting Summary Job Starting ===")

    # ── 1. Fetch Instagram content ──────────────────────────────────────────
    ig_username = os.getenv("INSTAGRAM_USERNAME", "")
    ig_password = os.getenv("INSTAGRAM_PASSWORD", "")
    fetcher = InstagramFetcher(username=ig_username, password=ig_password)
    items = fetcher.fetch_all()

    # ── 2. Analyse with Claude ──────────────────────────────────────────────
    anthropic_key = _require_env("ANTHROPIC_API_KEY")
    analyzer = WildlifeAnalyzer(api_key=anthropic_key)
    summary = analyzer.generate_summary(items)

    logger.info("\n--- SUMMARY ---\n%s\n--- END ---", summary)

    if dry_run:
        logger.info("Dry-run mode — WhatsApp message NOT sent.")
        return

    # ── 3. Send via WhatsApp ────────────────────────────────────────────────
    sender = WhatsAppSender(
        account_sid=_require_env("TWILIO_ACCOUNT_SID"),
        auth_token=_require_env("TWILIO_AUTH_TOKEN"),
        from_number=_require_env("TWILIO_WHATSAPP_FROM"),   # e.g. +14155238886
        to_number=_require_env("WHATSAPP_TO_NUMBER"),       # +919820839798
    )
    sid = sender.send(summary)
    logger.info("=== Job complete. Message SID(s): %s ===", sid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wildlife sighting WhatsApp summary")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without sending WhatsApp")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
