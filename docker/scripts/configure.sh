#!/bin/bash
# Runs as the one-shot `configurator` service on every `up`. Idempotent.
set -e
cd /home/frappe/frappe-bench

# Refresh assets from the image (the sites volume hides the baked ones).
mkdir -p sites/assets
rsync -a --delete /home/frappe/assets-baked/ sites/assets/
ls -1 apps > sites/apps.txt

bench set-config -g db_host "$DB_HOST"
bench set-config -gp db_port "$DB_PORT"
bench set-config -g redis_cache "redis://$REDIS_CACHE"
bench set-config -g redis_queue "redis://$REDIS_QUEUE"
bench set-config -g redis_socketio "redis://$REDIS_QUEUE"
bench set-config -gp socketio_port "$SOCKETIO_PORT"
echo "configured"
