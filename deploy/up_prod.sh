#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "> Starting prod stack (Postgres, Redis, API, Frontend, Webhook Gateway)"
docker compose -f docker-compose.prod.yml up -d --build

echo "Stack is up."
