#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=${ENV_FILE:-.env.prod}
echo "> Applying Django migrations"
docker compose --env-file "${ENV_FILE}" -f docker-compose.prod.yml exec -T api python manage.py migrate --noinput
echo "> Applying repuestos schema compatibility updates"
docker compose --env-file "${ENV_FILE}" -f docker-compose.prod.yml exec -T api python manage.py apply_repuestos_schema
echo "Migrations applied."
