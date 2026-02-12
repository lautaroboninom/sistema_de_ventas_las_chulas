#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "> Building production images (api, web, proxy)"
docker compose -f docker-compose.prod.yml build --pull

echo "Done."

