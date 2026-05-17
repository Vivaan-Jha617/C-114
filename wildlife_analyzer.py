from __future__ import annotations

"""
Analyses Instagram home feed content and produces a wildlife sighting bulletin
organised by park / tiger reserve name.
"""

import json
import logging
from datetime import datetime, timezone

import requests

from instagram_fetcher import ContentItem

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM = """You are an expert Indian wildlife naturalist producing a daily sighting bulletin.
Analyse the Instagram content provided and return a JSON object with two keys:

1. "bulletin" — an email-ready sighting update (max 1600 chars) organised STRICTLY by
   park or tiger reserve name. Extract park/reserve names from captions, hashtags
   (e.g. #bandhavgarh, #kabini, #ranthambore) and location tags.

   Format each park section exactly like this:

   🏕️ *Bandhavgarh Tiger Reserve*
   • 🐯 Tiger — adult male at waterhole, Zone B, 06:30
   • 🦌 Spotted Deer — herd of ~25, meadow area

   🏕️ *Kanha National Park*
   • 🐆 Leopard — brief sighting near buffer zone
   • 🦚 Peacock — displaying near Kanha village

   Rules:
   - One section per park. Merge sightings from multiple posts of the same park.
   - If park is unknown, group under 🏕️ *Park Unknown*.
   - Use species emoji where possible 🐯🐆🦁🐘🦌🐊🦅🦚🐍
   - End with a short closing line (e.g. total parks covered, best sighting of the day).
   - Skip any post with no wildlife content.

2. "captions" — a dict mapping each shortcode to a one-line wildlife caption
   (≤ 120 chars) that includes the park name and species. Set to null if no wildlife.

Respond with ONLY valid JSON. No markdown fences."""

USER_TEMPLATE = """Date: {date}
Source: Instagram home feed of @anandmihir (posts, reels and stories from all followed wildlife accounts)

Content from the last 24 hours:
{content}

Extract park/tiger reserve names from hashtags, location tags, and captions.
Organise the bulletin strictly by park name. Respond with JSON."""


def _fmt(items: list[ContentItem]) -> str:
    if not items:
        return "(No posts, reels or stories found in the last 24 hours.)"
    parts = []
    for it in items:
        ts = it.timestamp.strftime("%H:%M UTC")
        loc = f" | 📍{it.location}" if it.location else ""
        tags = " ".join(f"#{h}" for h in it.hashtags[:12])
        has_media = f"[{len(it.media_paths)} media]" if it.media_paths else "[no media]"
        parts.append(
            f"shortcode={it.shortcode} | {it.kind.upper()} @ {ts}{loc} {has_media}\n"
            f"Caption: {it.caption[:500] or '(none)'}\n"
            f"Tags: {tags or '—'}"
        )
    return "\n\n".join(parts)


def generate(items: list[ContentItem], api_key: str) -> tuple[str, dict[str, str | None]]:
    """Returns (bulletin_text, {shortcode: caption_or_None})."""
    date = datetime.now(tz=timezone.utc).strftime("%A, %d %B %Y")
    prompt = USER_TEMPLATE.format(date=date, content=_fmt(items))

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
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

    # Strip markdown fences if model adds them
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
        logger.warning("Non-JSON response — using raw text as bulletin.")
        bulletin = raw
        captions = {}

    logger.info("Bulletin: %d chars, captions for %d item(s).", len(bulletin), len(captions))
    return bulletin, captions
