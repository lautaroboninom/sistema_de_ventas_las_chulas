#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

STAMP=$(date +"%Y%m%d_%H%M%S")
FILE="/backups/backup_${STAMP}.dump"

echo "> Creating Postgres backup inside container: ${FILE}"
docker compose -f docker-compose.prod.yml exec -T db bash -lc 'mkdir -p /backups && pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c > '"${FILE}"

echo "Backup created. To copy to host:"
echo "  docker cp sepid-db:${FILE} ./db/backups/"

