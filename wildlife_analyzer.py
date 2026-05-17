"""
Uses Google Gemini (free tier) to analyse Instagram content and produce
a park-wide wildlife sighting bulletin + per-media captions.
"""

import json
import logging
from datetime import datetime, timezone

import google.generativeai as genai

from instagram_fetcher import ContentItem

logger = logging.getLogger(__name__)

SYSTEM = """You are an expert wildlife naturalist producing a daily park sighting bulletin.
Analyse the Instagram content provided and return a JSON object with two keys:

1. "bulletin" — a WhatsApp-ready park sighting update (max 1200 chars). Use:
   - Emoji species icons where helpful 🐯🦁🦌🐘
   - Short bullet points grouped by species or zone
   - A brief closing line

2. "captions" — a dict mapping each shortcode to a one-line wildlife caption
   (≤ 120 chars) for that post's photo/video. If a post has no wildlife, set
   its caption to null.

Respond with ONLY valid JSON. No markdown fences."""

USER_TEMPLATE = """Date: {date}
Instagram account: @anandmihir

Content from the last 24 hours:
{content}

Respond with JSON."""


def _fmt(items: list[ContentItem]) -> str:
    if not items:
        return "(No content found in the last 24 hours.)"
    parts = []
    for it in items:
        ts = it.timestamp.strftime("%H:%M UTC")
        loc = f" | 📍{it.location}" if it.location else ""
        tags = " ".join(f"#{h}" for h in it.hashtags[:8])
        has_media = f"[{len(it.media_paths)} media file(s)]" if it.media_paths else "[no media]"
        parts.append(
            f"shortcode={it.shortcode} | {it.kind.upper()} @ {ts}{loc} {has_media}\n"
            f"Caption: {it.caption[:400] or '(none)'}\n"
            f"Tags: {tags or '—'}"
        )
    return "\n\n".join(parts)


def generate(items: list[ContentItem], api_key: str) -> tuple[str, dict[str, str | None]]:
    """Returns (bulletin_text, {shortcode: caption_or_None})."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM,
    )

    date = datetime.now(tz=timezone.utc).strftime("%A, %d %B %Y")
    prompt = USER_TEMPLATE.format(date=date, content=_fmt(items))

    logger.info("Sending %d item(s) to Gemini.", len(items))
    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if Gemini adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
        bulletin = data.get("bulletin", "").strip()
        captions = data.get("captions", {})
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON — using raw text as bulletin.")
        bulletin = raw
        captions = {}

    logger.info("Bulletin: %d chars, captions for %d item(s).", len(bulletin), len(captions))
    return bulletin, captions
