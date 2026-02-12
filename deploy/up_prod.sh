#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=${ENV_FILE:-.env.prod}

# Ensure acme.json exists with correct permissions for Traefik
mkdir -p deploy/traefik
touch deploy/traefik/acme.json
chmod 600 deploy/traefik/acme.json || true

echo "> Starting stack (Traefik, DB, API, Web)"
docker compose --env-file "${ENV_FILE}" -f docker-compose.prod.yml up -d --build

echo "Stack is up."
