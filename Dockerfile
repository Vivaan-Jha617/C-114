FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY instagram_fetcher.py wildlife_analyzer.py email_sender.py run.py ./

# 9 PM IST = 15:30 UTC
RUN echo '30 15 * * * root . /app/.env.runtime && cd /app && python run.py >> /var/log/wildlife.log 2>&1' \
    > /etc/cron.d/wildlife \
    && chmod 0644 /etc/cron.d/wildlife

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/data"]

CMD ["/entrypoint.sh"]
