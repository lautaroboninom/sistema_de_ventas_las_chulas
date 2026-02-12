#!/usr/bin/env bash
set -euo pipefail

DOMAIN=${1:-reparacionesequilux.tailc98abd.ts.net}

echo "> Checking https://${DOMAIN}/"
curl -fsS --max-time 10 https://${DOMAIN}/ >/dev/null

echo "> Checking https://${DOMAIN}/api/health/"
curl -fsS --max-time 10 https://${DOMAIN}/api/health/ | grep -q '"ok"\s*:\s*true'

echo "Healthchecks passed."
