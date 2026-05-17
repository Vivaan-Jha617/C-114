#!/bin/sh
set -e

# Export Docker env vars into a file cron can source (cron has no env by default)
printenv \
  | grep -E "^(INSTAGRAM_|ANTHROPIC_|GREENAPI_|WHATSAPP_)" \
  | sed "s/'/'\\\\''/g; s/=\(.*\)/='\1'/" \
  > /app/.env.runtime

mkdir -p /data/media
touch /var/log/wildlife.log

echo "✅ Wildlife summary container started."
echo "   Next run: $(date -d 'today 15:30' '+%Y-%m-%d 15:30 UTC' 2>/dev/null || echo '15:30 UTC daily')"

# Stream cron logs to stdout so docker logs works
tail -F /var/log/wildlife.log &

exec cron -f
