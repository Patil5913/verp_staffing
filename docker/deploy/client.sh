#!/bin/bash
# ./client.sh <client> <up|down|logs|migrate|backup|create-site|add-app|bench ...> [args]
# Manages one client's lean stack (env: clients/<client>.env, project: <client>).
set -euo pipefail
cd "$(dirname "$0")"
C=${1:?client name}; CMD=${2:?command}; shift 2
[ -f "clients/$C.env" ] || { echo "missing clients/$C.env"; exit 1; }
dc() { docker compose -p "$C" --env-file "clients/$C.env" -f docker-compose.client.yml "$@"; }
case "$CMD" in
  up)      dc up -d ;;
  down)    dc down ;;   # keeps volumes
  logs)    dc logs -f "$@" ;;
  migrate) dc exec -T backend bench --site all migrate ;;
  create-site)
    SITE=${1:?site domain}; PW=${2:-$(openssl rand -base64 12)}
    set -a; source ../shared/.env; set +a
    dc exec -T backend bench new-site "$SITE" --admin-password "$PW" \
      --db-host verp-shared-db --db-root-username root --db-root-password "$DB_PASSWORD" \
      --mariadb-user-host-login-scope='%' --install-app verp_staffing
    dc exec -T backend bench --site "$SITE" enable-scheduler
    echo "Site: $SITE  Administrator password: $PW" ;;
  add-app) dc exec -T backend bench --site "${1:?site}" install-app "${2:?app}" ;;
  backup)  dc exec -T backend bench --site all backup --with-files ;;
  bench)   dc exec -T backend bench "$@" ;;
  *) echo "unknown command $CMD"; exit 1 ;;
esac
