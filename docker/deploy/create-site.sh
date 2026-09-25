#!/bin/bash
# ./create-site.sh <site-domain> [admin-password]
# Creates a tenant with verp_staffing installed. vruglechat is NOT installed.
set -euo pipefail
cd "$(dirname "$0")"
SITE=${1:?usage: ./create-site.sh <site-domain> [admin-password]}
ADMIN_PASSWORD=${2:-$(openssl rand -base64 12)}
set -a; source .env; set +a

docker compose exec -T backend test -d "sites/$SITE" && { echo "Site $SITE already exists"; exit 1; }

docker compose exec -T backend bench new-site "$SITE" \
  --mariadb-user-host-login-scope='%' \
  --admin-password "$ADMIN_PASSWORD" \
  --db-root-username root --db-root-password "$DB_PASSWORD" \
  --install-app verp_staffing

docker compose exec -T backend bench --site "$SITE" enable-scheduler

echo "Site: $SITE   Administrator password: $ADMIN_PASSWORD"
echo "Point DNS / your reverse proxy for $SITE at this server, port ${HTTP_PORT:-8080}."
