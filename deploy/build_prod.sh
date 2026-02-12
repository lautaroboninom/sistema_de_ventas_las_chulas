#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=${ENV_FILE:-.env.prod}

echo "> Building production images (api, web, proxy)"
docker compose --env-file "${ENV_FILE}" -f docker-compose.prod.yml build --pull

echo "Done."
