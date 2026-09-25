#!/bin/bash
# Build and push the image.
#   GIT_TOKEN=<gitea token with read access to verp_staffing + vruglechat> \
#   ./build.sh v1.0.0        (image defaults to parthpatil5/verp_staffing)
# Low-memory friendly: the frontend build is capped in each app's package.json.
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -eq 1 ]; then IMAGE=parthpatil5/verp_staffing; TAG=$1; else IMAGE=${1:?usage: ./build.sh [image] <tag>}; TAG=${2:?tag}; fi
: "${GIT_TOKEN:?set GIT_TOKEN}"

DOCKER_BUILDKIT=1 docker build \
  --secret id=git_token,env=GIT_TOKEN \
  --build-arg FRAPPE_VERSION="${FRAPPE_VERSION:-v15.119.1}" \
  --build-arg FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}" \
  -t "$IMAGE:$TAG" -t "$IMAGE:latest" .

docker push "$IMAGE:$TAG"
docker push "$IMAGE:latest"
