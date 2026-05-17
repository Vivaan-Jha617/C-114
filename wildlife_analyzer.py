"""
Uses Google Gemini (free tier) to analyse Instagram content and produce
a park-wide wildlife sighting bulletin + per-media captions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import requests

from instagram_fetcher import ContentItem

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM = """You are an expert wildlife naturalist producing a daily park sighting bulletin.
Analyse the Instagram content provided and return a JSON object with two keys:

1. "bulletin" — an email-ready park sighting update (max 1200 chars). Use:
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
    date = datetime.now(tz=timezone.utc).strftime("%A, %d %B %Y")
    prompt = SYSTEM + "\n\n" + USER_TEMPLATE.format(date=date, content=_fmt(items))

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 1024,
    }

    logger.info("Sending %d item(s) to Groq (Llama 3.3).", len(items))
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

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
