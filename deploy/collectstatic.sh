#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
echo "> Collecting static files"
docker compose -f docker-compose.prod.yml exec -T api python manage.py collectstatic --noinput
echo "Static collected (mounted on volume 'staticfiles')."

