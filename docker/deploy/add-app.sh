#!/bin/bash
# ./add-app.sh <site> vruglechat   -- install a baked-in app on one tenant.
set -euo pipefail
cd "$(dirname "$0")"
docker compose exec -T backend bench --site "${1:?site}" install-app "${2:?app}"
