from __future__ import annotations

"""
Fetches posts, reels and stories from all accounts @anandmihir follows,
downloaded with media, ready for wildlife analysis.
"""

import logging
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from instagrapi import Client

logger = logging.getLogger(__name__)

TARGET          = "anandmihir"
_DATA_DIR       = Path.home() / ".wildlife_summary"
MEDIA_DIR       = _DATA_DIR / "media"
SESSION_FILE    = str(_DATA_DIR / "ig_session.json")
MAX_MEDIA       = 15      # total media files to download per run
MAX_VIDEO_MB    = 15
MAX_IMAGE_MB    = 5
MAX_ACCOUNTS    = 80      # max followed accounts to check for posts
MAX_STORY_ACCS  = 30      # max followed accounts to check for stories
POSTS_PER_ACC   = 5       # most recent posts to fetch per account


@dataclass
class ContentItem:
    kind: str
    shortcode: str
    timestamp: datetime
    caption: str
    hashtags: list[str] = field(default_factory=list)
    location: str = ""
    url: str = ""
    media_paths: list[str] = field(default_factory=list)


def _cutoff() -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(hours=24)


def _make_client(username: str, session_id: str) -> Client:
    os.makedirs(_DATA_DIR, exist_ok=True)
    cl = Client()
    decoded = urllib.parse.unquote(session_id)
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login_by_sessionid(decoded)
            logger.info("Loaded saved session.")
            return cl
        except Exception:
            logger.warning("Saved session stale — re-authenticating.")
    cl.login_by_sessionid(decoded)
    cl.dump_settings(SESSION_FILE)
    logger.info("Authenticated via session cookie.")
    return cl


def _size_ok(path: Path, max_mb: float) -> bool:
    return path.exists() and path.stat().st_size <= max_mb * 1024 * 1024


def _download_media(cl: Client, media) -> list[str]:
    paths: list[str] = []
    try:
        if media.media_type == 1:            # photo
            p = cl.photo_download(media.pk, folder=MEDIA_DIR)
            if p and _size_ok(p, MAX_IMAGE_MB):
                paths.append(str(p))
        elif media.media_type == 2:          # video / reel
            p = cl.video_download(media.pk, folder=MEDIA_DIR)
            if p and _size_ok(p, MAX_VIDEO_MB):
                paths.append(str(p))
        elif media.media_type == 8:          # carousel
            ps = cl.album_download(media.pk, folder=MEDIA_DIR)
            for p in ps:
                if _size_ok(p, MAX_IMAGE_MB):
                    paths.append(str(p))
    except Exception as exc:
        logger.debug("Media download skipped: %s", exc)
    return paths


def _to_item(media, kind: str, total_media: int, cl: Client) -> tuple[ContentItem, int]:
    ts = media.taken_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    caption = media.caption_text or ""
    hashtags = [w[1:] for w in caption.split() if w.startswith("#")]
    loc = ""
    if hasattr(media, "location") and media.location:
        loc = getattr(media.location, "name", "") or ""

    media_paths: list[str] = []
    if total_media < MAX_MEDIA:
        media_paths = _download_media(cl, media)
        total_media += len(media_paths)

    shortcode = getattr(media, "code", str(media.pk))
    url = f"https://www.instagram.com/p/{shortcode}/" if kind != "story" else ""
    return ContentItem(
        kind=kind, shortcode=shortcode, timestamp=ts,
        caption=caption, hashtags=hashtags,
        location=loc, url=url, media_paths=media_paths,
    ), total_media


def fetch_all(username: str, password: str = "", session_id: str = "") -> list[ContentItem]:
    import shutil
    if MEDIA_DIR.exists():
        shutil.rmtree(MEDIA_DIR)
    MEDIA_DIR.mkdir(parents=True)

    cl = _make_client(username, session_id)
    my_user_id = cl.user_id_from_username(TARGET)
    cutoff = _cutoff()
    items: list[ContentItem] = []
    total_media = 0

    # ── Get list of followed accounts ────────────────────────────────────────
    try:
        following = cl.user_following(my_user_id, amount=MAX_ACCOUNTS)
        followed_ids = list(following.keys())
        logger.info("Found %d followed account(s) to scan.", len(followed_ids))
    except Exception as exc:
        logger.error("Could not get following list: %s", exc)
        followed_ids = []

    # ── Posts & Reels from each followed account ─────────────────────────────
    for i, uid in enumerate(followed_ids):
        try:
            medias = cl.user_medias_v1(uid, POSTS_PER_ACC)
            for media in medias:
                ts = media.taken_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
                kind = "reel" if media.media_type == 2 else "post"
                item, total_media = _to_item(media, kind, total_media, cl)
                items.append(item)
        except Exception as exc:
            logger.debug("Skipping account %s: %s", uid, exc)
        # Pause every 10 accounts to avoid rate limiting
        if i > 0 and i % 10 == 0:
            time.sleep(2)

    # ── Stories from followed accounts ───────────────────────────────────────
    for i, uid in enumerate(followed_ids[:MAX_STORY_ACCS]):
        try:
            stories = cl.user_stories(uid)
            for story in stories:
                ts = story.taken_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
                item, total_media = _to_item(story, "story", total_media, cl)
                items.append(item)
        except Exception as exc:
            logger.debug("Stories skipped for %s: %s", uid, exc)
        if i > 0 and i % 10 == 0:
            time.sleep(2)

    items.sort(key=lambda x: x.timestamp, reverse=True)
    logger.info(
        "Fetched %d item(s) from %d account(s), %d media file(s).",
        len(items), len(followed_ids), total_media,
    )
    return items
