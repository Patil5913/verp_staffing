#!/bin/bash
# ./create-site.sh <site-domain> [admin-password] [--db-host HOST] [--db-port PORT]
#
# Local DB (the `db` container):   ./create-site.sh tenant.example.com
# Client's DB on another server:   ./create-site.sh tenant.example.com --db-host 10.0.0.2 --db-port 3306
#   asks for that server's MariaDB root password (or set REMOTE_DB_ROOT_PASSWORD).
#   DB_USER_HOST_SCOPE (default '%') limits which host the site's DB user may
#   connect from, e.g. DB_USER_HOST_SCOPE=10.0.0.1 (this server, as the client's DB sees it).
# Installs verp_staffing only; vruglechat is added with ./add-app.sh.
set -euo pipefail
cd "$(dirname "$0")"

SITE=""; ADMIN_PASSWORD=""; DB_HOST_ARG=""; DB_PORT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --db-host) DB_HOST_ARG=${2:?--db-host needs a value}; shift 2;;
    --db-port) DB_PORT_ARG=${2:?--db-port needs a value}; shift 2;;
    -*) echo "unknown option $1"; exit 1;;
    *) if [ -z "$SITE" ]; then SITE=$1; elif [ -z "$ADMIN_PASSWORD" ]; then ADMIN_PASSWORD=$1; fi; shift;;
  esac
done
[ -n "$SITE" ] || { sed -n 2,4p "$0"; exit 1; }
[ -n "$ADMIN_PASSWORD" ] || ADMIN_PASSWORD=$(openssl rand -base64 12)

[ -f .env ] && { set -a; source .env; set +a; }

if [ -n "$DB_HOST_ARG" ]; then
  ROOT_PASSWORD=${REMOTE_DB_ROOT_PASSWORD:-}
  if [ -z "$ROOT_PASSWORD" ]; then read -r -s -p "MariaDB root password on $DB_HOST_ARG: " ROOT_PASSWORD; echo; fi
  DB_ARGS=(--db-host "$DB_HOST_ARG" --db-port "${DB_PORT_ARG:-3306}")
else
  ROOT_PASSWORD=${DB_PASSWORD:?set DB_PASSWORD in .env for the local db}
  DB_ARGS=()
fi

docker compose exec -T backend test -d "sites/$SITE" && { echo "Site $SITE already exists"; exit 1; }

docker compose exec -T backend bench new-site "$SITE" \
  --mariadb-user-host-login-scope="${DB_USER_HOST_SCOPE:-%}" \
  --admin-password "$ADMIN_PASSWORD" \
  --db-root-username root --db-root-password "$ROOT_PASSWORD" \
  "${DB_ARGS[@]}" \
  --install-app verp_staffing

docker compose exec -T backend bench --site "$SITE" enable-scheduler

echo "Site: $SITE   Administrator password: $ADMIN_PASSWORD"
[ -n "$DB_HOST_ARG" ] && echo "Database: $DB_HOST_ARG:${DB_PORT_ARG:-3306} (client server)"
echo "Point DNS / your reverse proxy for $SITE at this server, port ${HTTP_PORT:-8080}."
