#!/bin/bash
# Backs up all tenants (DB + files) into the sites volume: sites/<site>/private/backups
set -euo pipefail
cd "$(dirname "$0")"
docker compose exec -T backend bench --site all backup --with-files
