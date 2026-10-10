#!/bin/bash
# Keep the newest N backups of every site and delete the older ones.
#   prune-backups.sh <sites-dir> [keep]        (keep defaults to 5)
#
# A "backup" is the set of files bench writes together, which share one timestamp prefix, e.g.
#   20261010_101010-mysite_local-database.sql.gz, ...-site_config_backup.json, ...-files.tar, ...-private-files.tar
# so a backup is kept or deleted as a whole. Each site is counted on its own, and files that don't
# start with a timestamp are never touched.
set -euo pipefail

sites_dir="${1:?usage: prune-backups.sh <sites-dir> [keep]}"
keep="${2:-5}"

case "$keep" in ''|*[!0-9]*) echo "keep must be a number, got '$keep'" >&2; exit 1 ;; esac
if [ "$keep" -lt 1 ]; then echo "keep must be at least 1" >&2; exit 1; fi

for dir in "$sites_dir"/*/private/backups; do
  [ -d "$dir" ] || continue
  # timestamps present in this site's backups, newest first
  stamps=$(ls -1 "$dir" | grep -oE '^[0-9]{8}_[0-9]{6}' | sort -ru || true)
  [ -n "$stamps" ] || continue
  total=$(echo "$stamps" | wc -l)
  echo "    $(basename "$(dirname "$(dirname "$dir")")"): $total backup(s), keeping the newest $keep"
  echo "$stamps" | tail -n +"$((keep + 1))" | while read -r stamp; do
    find "$dir" -maxdepth 1 -type f -name "${stamp}-*" -print -delete
  done
done
