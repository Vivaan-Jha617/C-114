"""
Orchestrates the full pipeline: fetch Instagram → analyse → email with media.

Usage:
    python run.py            # full run
    python run.py --dry-run  # fetch + analyse + print, no email sent
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

import instagram_fetcher
import wildlife_analyzer
import email_sender

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        log.error("Missing required env var: %s", key)
        sys.exit(1)
    return val


def main(dry_run: bool = False) -> None:
    log.info("=== Wildlife Summary START ===")

    # 1. Fetch posts, reels, stories + download media
    items = instagram_fetcher.fetch_all(
        username=env("INSTAGRAM_USERNAME"),
        password=env("INSTAGRAM_PASSWORD"),
    )

    # 2. Gemini: generate bulletin + per-media captions
    bulletin, captions = wildlife_analyzer.generate(
        items=items,
        api_key=env("GROQ_API_KEY"),
    )

    # Collect all downloaded media paths across all items
    all_media: list[str] = []
    for item in sorted(items, key=lambda x: x.timestamp):
        all_media.extend(item.media_paths)

    date_str = datetime.now(tz=timezone.utc).strftime("%d %b %Y")
    log.info("\n=== BULLETIN (%s) ===\n%s\n===================", date_str, bulletin)

    if dry_run:
        log.info("Dry-run — email skipped. %d media file(s) ready.", len(all_media))
        return

    # 3. Send email with all media attached
    email_sender.send(
        from_email=env("EMAIL_FROM"),
        app_password=env("EMAIL_APP_PASSWORD"),
        to_email=env("EMAIL_TO"),
        bulletin=bulletin,
        media_paths=all_media,
    )
    log.info("=== Wildlife Summary DONE ===")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch and analyse but do not send email")
    main(dry_run=p.parse_args().dry_run)
