# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Scans Instagram account **@anandmihir** every day at **9 PM IST**, extracts wildlife sighting information from posts, reels, and stories using Claude AI, then sends a park-wide sighting bulletin to a WhatsApp number via Twilio.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with real credentials
```

## Running

```bash
# One-shot run (fetches, analyzes, sends WhatsApp)
python daily_summary.py

# Dry run — prints the generated bulletin without sending WhatsApp
python daily_summary.py --dry-run

# Long-running scheduler (fires daily at 9 PM IST / 15:30 UTC)
python scheduler.py
```

Production cron alternative (15:30 UTC = 9 PM IST):
```
30 15 * * * /path/to/.venv/bin/python /path/to/daily_summary.py >> /var/log/wildlife_summary.log 2>&1
```

## Architecture

The pipeline flows through four modules in sequence, orchestrated by `daily_summary.py`:

```
Instagram @anandmihir
    → instagram_fetcher.py   (instaloader; yields list[ContentItem])
    → wildlife_analyzer.py   (Claude API; returns plain-text bulletin string)
    → whatsapp_sender.py     (Twilio; splits at 1500 chars if needed)
```

**`ContentItem`** (defined in `instagram_fetcher.py`) is the shared data type between the fetcher and analyzer. It carries `content_type`, `caption`, `hashtags`, `timestamp`, `location`, and `url`.

**`InstagramFetcher`** — hardcoded to target `@anandmihir`. Login is optional; without credentials only public posts/reels are fetched (stories are skipped). Sessions are cached at `/tmp/.instaloader_session_{username}` to avoid repeated logins.

**`WildlifeAnalyzer`** — sends all `ContentItem`s as a single prompt to `claude-sonnet-4-6` with a system prompt that instructs it to act as a park naturalist. The prompt template caps output at 1500 characters so it fits in one WhatsApp message.

**`WhatsAppSender`** — wraps Twilio. Twilio requires numbers prefixed with `"whatsapp:"`. The `_split_message` helper splits on newline boundaries if the bulletin exceeds 1500 characters.

**`scheduler.py`** — thin wrapper using the `schedule` library. Fires `run()` daily at `"15:30"` UTC and polls every 30 seconds.

## Environment variables

All loaded via `python-dotenv` from `.env`. `daily_summary.py` calls `sys.exit(1)` if any required variable is missing.

| Variable | Required | Purpose |
|---|---|---|
| `INSTAGRAM_USERNAME` | No | Enables story fetching |
| `INSTAGRAM_PASSWORD` | No | Enables story fetching |
| `ANTHROPIC_API_KEY` | Yes | Claude API |
| `TWILIO_ACCOUNT_SID` | Yes (non-dry-run) | Twilio auth |
| `TWILIO_AUTH_TOKEN` | Yes (non-dry-run) | Twilio auth |
| `TWILIO_WHATSAPP_FROM` | Yes (non-dry-run) | Sender number (e.g. `+14155238886`) |
| `WHATSAPP_TO_NUMBER` | Yes (non-dry-run) | Recipient in E.164 format |

## Key constraints

- The Claude prompt instructs the model to keep output under 1500 characters. If you change the model or prompt, verify the bulletin still fits in one WhatsApp message.
- `fetch_posts_and_reels` stops iterating as soon as it sees a post older than 24 hours (relies on Instagram returning posts in reverse-chronological order).
- The Twilio sandbox number (`+14155238886`) requires the recipient to first send a join code. Production use needs a dedicated WhatsApp-enabled Twilio number.
