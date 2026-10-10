#!/bin/bash
# Full release update for every tenant:
#   1. take fresh backups (DB + files) of all sites
#   2. prune old backups: the newest BACKUPS_TO_KEEP (default 5) per site are kept, older ones deleted
#      (only after the new ones succeeded)
#   3. put all sites in maintenance mode
#   4. docker compose pull + up -d (restart on the new image)
#   5. migrate all sites
#   6. turn maintenance mode off
# If anything fails the script stops with maintenance mode still ON, so users
# never hit a half-migrated site. Fix the problem, then run:
#   docker compose exec -T backend bench --site all set-maintenance-mode off
set -euo pipefail
cd "$(dirname "$0")"

# Run a bench command inside the running backend container.
bench() { docker compose exec -T backend bench "$@"; }

echo "==> [1/6] Taking new backups of all sites"
# Create a timestamp file so step 2 can check that new backups really were written.
docker compose exec -T backend bash -c 'touch /home/frappe/frappe-bench/sites/.backup-marker'
bench --site all backup --with-files

KEEP="${BACKUPS_TO_KEEP:-5}"
echo "==> [2/6] Pruning old backups (keeping the newest $KEEP per site)"
# Safety check: only prune if new backups really exist.
found=$(docker compose exec -T backend bash -c 'cd /home/frappe/frappe-bench/sites && find . -path "*/private/backups/*" -type f -newer .backup-marker | wc -l')
if [ "$found" -eq 0 ]; then echo "No new backup files found, refusing to delete old ones" >&2; exit 1; fi
docker compose exec -T backend rm -f /home/frappe/frappe-bench/sites/.backup-marker
# The script runs inside the container (read from stdin), counting backups per site.
docker compose exec -T backend bash -s -- /home/frappe/frappe-bench/sites "$KEEP" < prune-backups.sh

# From here on visitors see the "Updating" page instead of a half-updated site.
echo "==> [3/6] Enabling maintenance mode on all sites"
bench --site all set-maintenance-mode on

# Maintenance flags live in the sites volume, so they survive the restart.
# The new image (code) only takes effect once the containers are recreated.
echo "==> [4/6] Pulling images and restarting"
docker compose pull
docker compose up -d --remove-orphans

# Wait until the new backend answers, otherwise migrate would fail on startup.
echo "    waiting for backend..."
for _ in $(seq 1 60); do
  if docker compose exec -T backend bench --site all list-apps >/dev/null 2>&1; then break; fi
  sleep 5
done

# Applies the new code's schema/patches to every site (hooks.py, doctypes, patches).
echo "==> [5/6] Migrating all sites"
bench --site all migrate

# Only reached if everything above succeeded (set -e stops the script otherwise).
echo "==> [6/6] Disabling maintenance mode on all sites"
bench --site all set-maintenance-mode off

echo "Done."
