#!/bin/bash
# Wildlife Summary — Mac Setup
# Run once: bash setup_mac.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=$(which python3)
LOG="$HOME/wildlife_summary.log"
PLIST="$HOME/Library/LaunchAgents/com.wildlife.summary.plist"

echo "=== Wildlife Summary Setup (Mac) ==="

# Install dependencies
echo "Installing Python dependencies..."
$PYTHON -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Verify .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file not found in $SCRIPT_DIR"
  echo "Please create it from .env.example first."
  exit 1
fi

# Create launchd plist (runs every day at 9:00 PM local time)
cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wildlife.summary</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$SCRIPT_DIR/run.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$SCRIPT_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>21</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG</string>
  <key>StandardErrorPath</key>
  <string>$LOG</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF

# Load it
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "✅ Done! Wildlife summary will run every day at 9:00 PM."
echo "   Logs: $LOG"
echo ""
echo "Test it now with:  python3 $SCRIPT_DIR/run.py --dry-run"
