# Wildlife Sighting WhatsApp Summary

Scans Instagram account **@anandmihir** every day at **9 PM IST**, extracts wildlife
sighting information from posts, reels, and stories, then WhatsApps a park-wide
sighting bulletin to **+91 98208 39798**.

## How it works

```
Instagram @anandmihir  ──►  instagram_fetcher.py
                                     │
                                     ▼
                           wildlife_analyzer.py  (Claude AI)
                                     │
                                     ▼
                           whatsapp_sender.py  (Twilio)
                                     │
                                     ▼
                         WhatsApp +919820839798 @ 9 PM IST
```

## Setup

### 1. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:

| Variable | Description |
|---|---|
| `INSTAGRAM_USERNAME` | Your Instagram login (needed for stories) |
| `INSTAGRAM_PASSWORD` | Your Instagram password |
| `ANTHROPIC_API_KEY` | Claude API key from console.anthropic.com |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender number (e.g. `+14155238886`) |
| `WHATSAPP_TO_NUMBER` | Recipient number in E.164 format (`+919820839798`) |

### 3. Twilio WhatsApp setup
1. Sign up at [twilio.com](https://www.twilio.com)
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Join the Twilio sandbox by sending the join code from +919820839798 to the sandbox number
4. For production, provision a dedicated WhatsApp-enabled number

### 4. Run

**One-shot (now):**
```bash
python daily_summary.py
```

**Dry run (no WhatsApp sent):**
```bash
python daily_summary.py --dry-run
```

**Continuous scheduler (runs every day at 9 PM IST):**
```bash
python scheduler.py
```

**Production — systemd service or cron:**

Cron alternative (runs at 15:30 UTC = 9 PM IST):
```
30 15 * * * /path/to/.venv/bin/python /path/to/daily_summary.py >> /var/log/wildlife_summary.log 2>&1
```

## File overview

| File | Purpose |
|---|---|
| `instagram_fetcher.py` | Fetches posts, reels, stories via instaloader |
| `wildlife_analyzer.py` | Claude-powered wildlife sighting extraction & summary |
| `whatsapp_sender.py` | Sends the bulletin via Twilio WhatsApp API |
| `daily_summary.py` | Orchestrates the full pipeline |
| `scheduler.py` | Long-running process that triggers the job at 9 PM IST |
