#!/bin/bash
# Full release update for every tenant:
#   1. take fresh backups (DB + files) of all sites
#   2. delete the older backups (only after the new ones succeeded)
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
# Create a timestamp file. Anything newer than it is a new backup;
# anything older is a previous backup that step 2 may delete.
# Marker so step 2 can tell new backups from old ones.
docker compose exec -T backend bash -c 'touch /home/frappe/frappe-bench/sites/.backup-marker'
bench --site all backup --with-files

echo "==> [2/6] Deleting previous backups (keeping the ones just taken)"
docker compose exec -T backend bash -c '
  cd /home/frappe/frappe-bench/sites
  # Safety check: only delete old backups if new ones really exist.
  found=$(find . -path "*/private/backups/*" -type f -newer .backup-marker | wc -l)
  if [ "$found" -eq 0 ]; then echo "No new backup files found, refusing to delete old ones" >&2; exit 1; fi
  find . -path "*/private/backups/*" -type f ! -newer .backup-marker -print -delete
  rm -f .backup-marker
'

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
