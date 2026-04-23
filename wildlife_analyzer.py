"""
Analyzes Instagram content for wildlife sightings using the Claude API
and generates a park-wide sighting update summary.
"""

import json
import logging
from datetime import datetime, timezone

import anthropic

from instagram_fetcher import ContentItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert wildlife naturalist and park ranger assistant.
Your job is to analyze social media content from a wildlife photographer/naturalist
and extract all wildlife sighting information to produce a clear, engaging daily park
sighting update.

For each piece of content, identify:
- Species sighted (common name + scientific name if determinable)
- Location / zone within the park (if mentioned)
- Number of individuals seen (if mentioned)
- Notable behaviour (hunting, feeding, mating, with cubs/young, etc.)
- Time of sighting (if mentioned)
- Any other noteworthy details (rare species, unusual behaviour, exceptional photography conditions)

Produce the final summary in the style of an official park daily sighting bulletin,
suitable for sharing with wildlife enthusiasts and tourists via WhatsApp.
Use clear section headings, bullet points, and an upbeat, professional tone.
If no wildlife content is found, say so clearly.
"""

ANALYSIS_PROMPT_TEMPLATE = """Below is all the Instagram content posted by @anandmihir in the last 24 hours.
Analyse each item for wildlife sightings and then produce a single consolidated
"Park Wildlife Sighting Update" for today ({date}).

Content items:
{content}

---
Produce the WhatsApp-ready bulletin now. Start with a title line, then list sightings
by species or zone, and end with a short closing note. Keep it under 1500 characters
so it fits comfortably in one WhatsApp message."""


def _format_content_for_prompt(items: list[ContentItem]) -> str:
    if not items:
        return "(No posts, reels, or stories found in the last 24 hours.)"
    parts: list[str] = []
    for i, item in enumerate(items, 1):
        ts = item.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        tags = " ".join(f"#{h}" for h in item.hashtags[:10])
        loc = f" | Location: {item.location}" if item.location else ""
        parts.append(
            f"[{i}] Type: {item.content_type.upper()} | Time: {ts}{loc}\n"
            f"Caption: {item.caption[:600] or '(no caption)'}\n"
            f"Tags: {tags or '(none)'}"
        )
    return "\n\n".join(parts)


class WildlifeAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_summary(self, items: list[ContentItem]) -> str:
        today = datetime.now(tz=timezone.utc).strftime("%A, %d %B %Y")
        content_block = _format_content_for_prompt(items)
        user_prompt = ANALYSIS_PROMPT_TEMPLATE.format(date=today, content=content_block)

        logger.info("Sending %d content item(s) to Claude for wildlife analysis.", len(items))
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        summary = response.content[0].text.strip()
        logger.info("Wildlife summary generated (%d characters).", len(summary))
        return summary
