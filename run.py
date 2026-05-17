"""
Orchestrates the full pipeline: fetch Instagram → analyse → WhatsApp with media.

Usage:
    python run.py            # full run
    python run.py --dry-run  # fetch + analyse + print, no WhatsApp
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

import instagram_fetcher
import wildlife_analyzer
import whatsapp_sender

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

    # 2. Claude: generate bulletin + per-media captions
    bulletin, captions = wildlife_analyzer.generate(
        items=items,
        api_key=env("ANTHROPIC_API_KEY"),
    )

    date_str = datetime.now(tz=timezone.utc).strftime("%d %b %Y")
    header = f"🌿 *Wildlife Sighting Update — {date_str}*\nSightings from @anandmihir:"

    # Print for logs regardless
    log.info("\n%s\n%s", header, bulletin)
    for sc, cap in captions.items():
        if cap:
            log.info("  [%s] %s", sc, cap)

    if dry_run:
        log.info("Dry-run — WhatsApp skipped.")
        return

    # 3. Send via Green API (header + media files + bulletin)
    client = whatsapp_sender.GreenAPIClient(
        instance_id=env("GREENAPI_INSTANCE_ID"),
        api_token=env("GREENAPI_API_TOKEN"),
        to_number=env("WHATSAPP_TO_NUMBER"),   # e.g. 919820839798
    )
    whatsapp_sender.send_summary(
        client=client,
        items=items,
        bulletin=bulletin,
        captions=captions,
        header=header,
    )
    log.info("=== Wildlife Summary DONE ===")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch and analyse but do not send WhatsApp")
    main(dry_run=p.parse_args().dry_run)
