#!/bin/bash

echo "[INFO] Parsing config.yaml for schedule..."
HOUR=$(python3 -c "import yaml; print(yaml.safe_load(open('/app/config.yaml'))['schedule']['hour'])")
MINUTE=$(python3 -c "import yaml; print(yaml.safe_load(open('/app/config.yaml'))['schedule']['minute'])")

echo "[INFO] Generating crontab: $MINUTE $HOUR * * *"

echo "SHELL=/bin/bash" > /etc/cron.d/embyjob
echo "$MINUTE $HOUR * * * root python3 /app/main.py >> /var/log/cron.log 2>&1" >> /etc/cron.d/embyjob
chmod 0644 /etc/cron.d/embyjob
crontab /etc/cron.d/embyjob

touch /var/log/cron.log
cron
tail -f /var/log/cron.log
