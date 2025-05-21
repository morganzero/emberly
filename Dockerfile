# Dockerfile
FROM python:3.12-slim

LABEL maintainer="Emberly Project"
LABEL description="Trend-aware symlink library manager for Emby"

RUN apt-get update && apt-get install -y cron jq curl && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Startar cron och genererar crontab från config.yaml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
