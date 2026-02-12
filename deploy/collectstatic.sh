#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=${ENV_FILE:-.env.prod}
echo "> Collecting static files"
docker compose --env-file "${ENV_FILE}" -f docker-compose.prod.yml exec -T api python manage.py collectstatic --noinput
echo "Static collected (mounted on volume 'staticfiles')."
