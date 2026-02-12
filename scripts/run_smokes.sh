#!/usr/bin/env bash
set -euo pipefail

: "${API_URL:=http://localhost:18000}"
echo "Running smoke tests against ${API_URL}" >&2

docker compose exec sistemadereparaciones-api bash -lc "API_URL='${API_URL}' python - <<'PY'
import os
os.environ.setdefault('API_URL', os.getenv('API_URL','http://localhost:18000'))
from tests.smokes.run_smokes import run_flow
out = run_flow()
print(out)
PY"

