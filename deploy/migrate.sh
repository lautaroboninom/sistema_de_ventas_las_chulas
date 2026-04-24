#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
echo "> Applying Django migrations"
docker compose -f docker-compose.prod.yml exec -T api python manage.py migrate --noinput
echo "> Applying pending SQL patches"
docker compose -f docker-compose.prod.yml exec -T api python manage.py apply_sql_patches
echo "Migrations applied."

