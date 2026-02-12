$ErrorActionPreference = "Stop"

# API_URL uses host:port from compose by default
if (-not $env:API_URL) {
  $env:API_URL = "http://localhost:18000"
}

Write-Host "Running smoke tests against $env:API_URL" -ForegroundColor Cyan

docker compose exec sistemadereparaciones-api bash -lc "python - <<'PY'
import os, sys
os.environ.setdefault('API_URL', os.getenv('API_URL','http://localhost:18000'))
from tests.smokes.run_smokes import run_flow
out = run_flow()
print(out)
PY"

