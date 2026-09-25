#!/bin/bash
# Run after pulling a new image and `docker compose up -d`: migrates every tenant.
set -euo pipefail
cd "$(dirname "$0")"
docker compose exec -T backend bench --site all migrate
