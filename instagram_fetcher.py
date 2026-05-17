from __future__ import annotations

"""
Fetches posts, reels, and stories from @anandmihir using instagrapi
(Instagram mobile API — not blocked like instaloader's GraphQL).
"""

import logging
import os
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

logger = logging.getLogger(__name__)

TARGET = "anandmihir"
_DATA_DIR = Path.home() / ".wildlife_summary"
MEDIA_DIR = _DATA_DIR / "media"
SESSION_FILE = str(_DATA_DIR / "ig_session.json")
MAX_MEDIA = 10
MAX_VIDEO_MB = 15
MAX_IMAGE_MB = 5


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

    # Try loading saved session first
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login_by_sessionid(decoded)
            logger.info("Loaded saved instagrapi session.")
            return cl
        except Exception:
            logger.warning("Saved session stale — re-authenticating.")

    cl.login_by_sessionid(decoded)
    cl.dump_settings(SESSION_FILE)
    logger.info("Authenticated with session cookie via instagrapi.")
    return cl


def _size_ok(path: Path, max_mb: float) -> bool:
    return path.exists() and path.stat().st_size <= max_mb * 1024 * 1024


def fetch_all(username: str, password: str = "", session_id: str = "") -> list[ContentItem]:
    import shutil
    if MEDIA_DIR.exists():
        shutil.rmtree(MEDIA_DIR)
    MEDIA_DIR.mkdir(parents=True)

    cl = _make_client(username, session_id)
    user_id = cl.user_id_from_username(TARGET)
    cutoff = _cutoff()
    items: list[ContentItem] = []
    total_media = 0

    # ── Posts & Reels — fetch ONLY @anandmihir's own posts ───────────────────
    try:
        # user_medias_v1 calls /api/v1/feed/user/{id}/ — only that user's posts
        medias = cl.user_medias_v1(user_id, 30)
    except Exception as exc:
        logger.error("Failed to fetch posts: %s", exc)
        medias = []

    for media in medias:
        ts = media.taken_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue

        kind = "reel" if media.media_type == 2 else "post"
        caption = media.caption_text or ""
        hashtags = [w[1:] for w in caption.split() if w.startswith("#")]
        loc = ""
        if media.location:
            loc = getattr(media.location, "name", "") or ""
        url = f"https://www.instagram.com/p/{media.code}/"

        media_paths: list[str] = []
        if total_media < MAX_MEDIA:
            try:
                if media.media_type == 1:          # photo
                    p = cl.photo_download(media.pk, folder=MEDIA_DIR)
                    if p and _size_ok(p, MAX_IMAGE_MB):
                        media_paths.append(str(p))
                elif media.media_type == 2:        # video / reel
                    p = cl.video_download(media.pk, folder=MEDIA_DIR)
                    if p and _size_ok(p, MAX_VIDEO_MB):
                        media_paths.append(str(p))
                elif media.media_type == 8:        # carousel
                    paths = cl.album_download(media.pk, folder=MEDIA_DIR)
                    for p in paths:
                        if _size_ok(p, MAX_IMAGE_MB):
                            media_paths.append(str(p))
            except Exception as exc:
                logger.warning("Media download failed for %s: %s", media.code, exc)
            total_media += len(media_paths)

        items.append(ContentItem(
            kind=kind, shortcode=media.code, timestamp=ts,
            caption=caption, hashtags=hashtags,
            location=loc, url=url, media_paths=media_paths,
        ))

    # ── Stories ──────────────────────────────────────────────────────────────
    try:
        stories = cl.user_stories(user_id)
        for story in stories:
            ts = story.taken_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            caption = story.caption_text or ""
            hashtags = [w[1:] for w in caption.split() if w.startswith("#")]
            media_paths = []
            if total_media < MAX_MEDIA:
                try:
                    if story.media_type == 1:
                        p = cl.photo_download(story.pk, folder=MEDIA_DIR)
                        if p and _size_ok(p, MAX_IMAGE_MB):
                            media_paths.append(str(p))
                    else:
                        p = cl.video_download(story.pk, folder=MEDIA_DIR)
                        if p and _size_ok(p, MAX_VIDEO_MB):
                            media_paths.append(str(p))
                except Exception as exc:
                    logger.warning("Story download failed: %s", exc)
                total_media += len(media_paths)
            items.append(ContentItem(
                kind="story", shortcode=str(story.pk), timestamp=ts,
                caption=caption, hashtags=hashtags, media_paths=media_paths,
            ))
    except Exception as exc:
        logger.warning("Could not fetch stories: %s", exc)

    items.sort(key=lambda x: x.timestamp, reverse=True)
    logger.info("Fetched %d item(s), %d media file(s).", len(items), total_media)
    return items
