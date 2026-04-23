"""
Instagram content fetcher for @anandmihir.
Fetches posts, reels, and stories from the last 24 hours using instaloader.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

import instaloader

logger = logging.getLogger(__name__)


@dataclass
class ContentItem:
    content_type: str  # "post", "reel", "story"
    shortcode: str
    timestamp: datetime
    caption: str
    hashtags: list[str] = field(default_factory=list)
    url: str = ""
    media_type: str = ""  # "image", "video", "sidecar"
    location: str = ""


class InstagramFetcher:
    def __init__(self, username: str, password: str | None = None):
        self.target_account = "anandmihir"
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )
        self._login(username, password)

    def _login(self, username: str, password: str | None) -> None:
        if not username or not password:
            logger.info("No credentials provided — fetching public content only (no stories).")
            return
        try:
            session_file = f"/tmp/.instaloader_session_{username}"
            if os.path.exists(session_file):
                self.loader.load_session_from_file(username, session_file)
                logger.info("Loaded existing Instagram session.")
            else:
                self.loader.login(username, password)
                self.loader.save_session_to_file(session_file)
                logger.info("Logged in to Instagram and saved session.")
        except instaloader.exceptions.BadCredentialsException:
            logger.error("Invalid Instagram credentials.")
            raise
        except Exception as exc:
            logger.warning("Could not log in to Instagram: %s — stories will be skipped.", exc)

    def _cutoff(self) -> datetime:
        return datetime.now(tz=timezone.utc) - timedelta(hours=24)

    def fetch_posts_and_reels(self) -> list[ContentItem]:
        """Fetch posts and reels from the last 24 hours."""
        items: list[ContentItem] = []
        cutoff = self._cutoff()
        try:
            profile = instaloader.Profile.from_username(self.loader.context, self.target_account)
            for post in profile.get_posts():
                post_time = post.date_utc.replace(tzinfo=timezone.utc)
                if post_time < cutoff:
                    break
                content_type = "reel" if post.is_video and post.video_url else "post"
                location = ""
                if post.location:
                    location = getattr(post.location, "name", "") or ""
                items.append(ContentItem(
                    content_type=content_type,
                    shortcode=post.shortcode,
                    timestamp=post_time,
                    caption=post.caption or "",
                    hashtags=list(post.caption_hashtags),
                    url=f"https://www.instagram.com/p/{post.shortcode}/",
                    media_type="video" if post.is_video else ("sidecar" if post.typename == "GraphSidecar" else "image"),
                    location=location,
                ))
        except Exception as exc:
            logger.error("Error fetching posts/reels: %s", exc)
        return items

    def fetch_stories(self) -> list[ContentItem]:
        """Fetch stories from the last 24 hours (requires login)."""
        items: list[ContentItem] = []
        if not self.loader.context.is_logged_in:
            logger.info("Skipping stories — not logged in.")
            return items
        cutoff = self._cutoff()
        try:
            profile = instaloader.Profile.from_username(self.loader.context, self.target_account)
            for story in self.loader.get_stories(userids=[profile.userid]):
                for item in story.get_items():
                    story_time = item.date_utc.replace(tzinfo=timezone.utc)
                    if story_time < cutoff:
                        continue
                    items.append(ContentItem(
                        content_type="story",
                        shortcode=item.mediaid,
                        timestamp=story_time,
                        caption=item.caption or "",
                        hashtags=list(item.caption_hashtags) if item.caption else [],
                        media_type="video" if item.is_video else "image",
                    ))
        except Exception as exc:
            logger.error("Error fetching stories: %s", exc)
        return items

    def fetch_all(self) -> list[ContentItem]:
        """Return all content from the last 24 hours, sorted newest first."""
        posts = self.fetch_posts_and_reels()
        stories = self.fetch_stories()
        all_items = posts + stories
        all_items.sort(key=lambda x: x.timestamp, reverse=True)
        logger.info(
            "Fetched %d item(s) from @%s: %d post/reel, %d story.",
            len(all_items), self.target_account, len(posts), len(stories),
        )
        return all_items
