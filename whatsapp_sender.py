"""
WhatsApp sender using Green API (free tier).
Supports plain text messages AND media file uploads (images + videos).

Setup:
  1. Sign up at https://green-api.com (free: 500 messages/month)
  2. Create an instance → scan QR code to link your WhatsApp
  3. Copy Instance ID and API Token into .env
"""

import logging
import mimetypes
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.green-api.com/waInstance{iid}/{method}/{token}"
_SEND_TIMEOUT = 30
_UPLOAD_TIMEOUT = 120


class GreenAPIClient:
    def __init__(self, instance_id: str, api_token: str, to_number: str):
        self.iid = instance_id
        self.token = api_token
        # Green API chat ID format: countrycode+number@c.us (no leading +)
        self.chat_id = f"{to_number.lstrip('+')}@c.us"

    def _url(self, method: str) -> str:
        return _BASE.format(iid=self.iid, method=method, token=self.token)

    def send_text(self, message: str) -> None:
        chunks = _split(message)
        for chunk in chunks:
            r = requests.post(
                self._url("sendMessage"),
                json={"chatId": self.chat_id, "message": chunk},
                timeout=_SEND_TIMEOUT,
            )
            r.raise_for_status()
            logger.info("Text sent (%d chars) — idMessage: %s",
                        len(chunk), r.json().get("idMessage"))

    def send_media(self, file_path: str, caption: str = "") -> None:
        path = Path(file_path)
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or ("video/mp4" if path.suffix == ".mp4" else "image/jpeg")
        file_size_mb = path.stat().st_size / (1024 * 1024)
        logger.info("Uploading %s (%.1f MB)…", path.name, file_size_mb)
        with open(path, "rb") as fh:
            r = requests.post(
                self._url("sendFileByUpload"),
                data={"chatId": self.chat_id, "caption": caption[:1024]},
                files={"file": (path.name, fh, mime)},
                timeout=_UPLOAD_TIMEOUT,
            )
        r.raise_for_status()
        logger.info("Media sent: %s — idMessage: %s",
                    path.name, r.json().get("idMessage"))


def send_summary(
    client: GreenAPIClient,
    items,                          # list[ContentItem]
    bulletin: str,
    captions: dict[str, str | None],
    header: str = "",
) -> None:
    """
    Send the full wildlife update:
      1. Optional header message
      2. Each piece of media (image/video) with its AI caption
      3. The full text bulletin
    """
    if header:
        client.send_text(header)

    # Send media files in chronological order (oldest first = natural story flow)
    ordered = sorted(items, key=lambda x: x.timestamp)
    for item in ordered:
        caption = captions.get(item.shortcode)
        for media_path in item.media_paths:
            if not os.path.exists(media_path):
                continue
            label = caption or item.caption[:120] or ""
            try:
                client.send_media(media_path, caption=label)
            except Exception as exc:
                logger.warning("Failed to send %s: %s", media_path, exc)

    # Final text bulletin
    client.send_text(bulletin)


def _split(text: str, max_len: int = 1400) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts
