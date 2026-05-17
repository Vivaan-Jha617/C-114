"""
Fetches posts, reels, and stories from @anandmihir in the last 24 hours,
downloading all media (images/videos) to a local temp directory.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import instaloader

logger = logging.getLogger(__name__)

TARGET = "anandmihir"
_DATA_DIR = Path.home() / ".wildlife_summary"
SESSION_FILE = str(_DATA_DIR / "ig_session")
MEDIA_DIR = _DATA_DIR / "media"
MAX_MEDIA = 10          # cap total downloaded files per run
MAX_VIDEO_MB = 15       # skip videos larger than this
MAX_IMAGE_MB = 5


@dataclass
class ContentItem:
    kind: str               # post | reel | story
    shortcode: str
    timestamp: datetime
    caption: str
    hashtags: list[str] = field(default_factory=list)
    location: str = ""
    url: str = ""
    media_paths: list[str] = field(default_factory=list)   # local files


def _cutoff() -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(hours=24)


def _make_loader() -> instaloader.Instaloader:
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=True,
        max_connection_attempts=3,
    )


def _login(loader: instaloader.Instaloader, username: str, session_id: str) -> bool:
    """Authenticate using browser session cookie. Returns True on success."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    try:
        import urllib.parse
        # Decode URL-encoded cookie value (e.g. %3A → :)
        decoded = urllib.parse.unquote(session_id)
        loader.context.update_cookies({"sessionid": decoded})
        loader.context.username = username
        logger.info("Authenticated via session cookie.")
        return True
    except Exception as exc:
        logger.warning("Session cookie login failed (%s) — stories will be skipped.", exc)
        return False


def _download(url: str, dest: Path, max_mb: float) -> str | None:
    if dest.exists():
        return str(dest)
    try:
        with requests.get(url, stream=True, timeout=60,
                          headers={"User-Agent": "Mozilla/5.0"}) as r:
            r.raise_for_status()
            size = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    size += len(chunk)
                    if size > max_mb * 1024 * 1024:
                        logger.warning("Skipping %s — exceeds %s MB limit.", dest.name, max_mb)
                        dest.unlink(missing_ok=True)
                        return None
                    f.write(chunk)
        logger.debug("Downloaded %s (%.1f KB)", dest.name, size / 1024)
        return str(dest)
    except Exception as exc:
        logger.warning("Download failed for %s: %s", dest.name, exc)
        dest.unlink(missing_ok=True)
        return None


def _get_post_media(post: instaloader.Post, media_dir: Path) -> list[str]:
    paths: list[str] = []
    sc = post.shortcode

    if post.typename == "GraphSidecar":
        for i, node in enumerate(post.get_sidecar_nodes()):
            if node.is_video:
                p = _download(node.video_url,
                              media_dir / f"{sc}_{i}.mp4", MAX_VIDEO_MB)
            else:
                p = _download(node.display_url,
                              media_dir / f"{sc}_{i}.jpg", MAX_IMAGE_MB)
            if p:
                paths.append(p)
    elif post.is_video:
        p = _download(post.video_url, media_dir / f"{sc}.mp4", MAX_VIDEO_MB)
        if p:
            paths.append(p)
    else:
        p = _download(post.url, media_dir / f"{sc}.jpg", MAX_IMAGE_MB)
        if p:
            paths.append(p)

    return paths


def _get_story_media(item, media_dir: Path) -> list[str]:
    mid = str(item.mediaid)
    if item.is_video:
        p = _download(item.video_url, media_dir / f"story_{mid}.mp4", MAX_VIDEO_MB)
    else:
        p = _download(item.url, media_dir / f"story_{mid}.jpg", MAX_IMAGE_MB)
    return [p] if p else []


def fetch_all(username: str, password: str, session_id: str = "") -> list[ContentItem]:
    # Fresh media dir each run
    if MEDIA_DIR.exists():
        shutil.rmtree(MEDIA_DIR)
    MEDIA_DIR.mkdir(parents=True)

    loader = _make_loader()
    logged_in = _login(loader, username, session_id or password)
    profile = instaloader.Profile.from_username(loader.context, TARGET)
    cutoff = _cutoff()
    items: list[ContentItem] = []
    total_media = 0

    # ── Posts & Reels ────────────────────────────────────────────────────────
    for post in profile.get_posts():
        ts = post.date_utc.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            break
        if total_media < MAX_MEDIA:
            media = _get_post_media(post, MEDIA_DIR)
            total_media += len(media)
        else:
            media = []
        kind = "reel" if post.is_video else "post"
        loc = getattr(post.location, "name", "") if post.location else ""
        items.append(ContentItem(
            kind=kind, shortcode=post.shortcode, timestamp=ts,
            caption=post.caption or "", hashtags=list(post.caption_hashtags),
            location=loc, url=f"https://www.instagram.com/p/{post.shortcode}/",
            media_paths=media,
        ))

    # ── Stories (only if logged in) ──────────────────────────────────────────
    if not logged_in:
        logger.info("Skipping stories — not logged in.")
    for story in (loader.get_stories(userids=[profile.userid]) if logged_in else []):
        for item in story.get_items():
            ts = item.date_utc.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            if total_media < MAX_MEDIA:
                media = _get_story_media(item, MEDIA_DIR)
                total_media += len(media)
            else:
                media = []
            items.append(ContentItem(
                kind="story", shortcode=str(item.mediaid), timestamp=ts,
                caption=item.caption or "",
                hashtags=list(item.caption_hashtags) if item.caption else [],
                media_paths=media,
            ))

    items.sort(key=lambda x: x.timestamp, reverse=True)
    logger.info(
        "Fetched %d item(s) from @%s, downloaded %d media file(s).",
        len(items), TARGET, total_media,
    )
    return items
