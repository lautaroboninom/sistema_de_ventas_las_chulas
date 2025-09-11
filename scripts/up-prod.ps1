$ErrorActionPreference = "Stop"

# Variables
$compose = @("-f","docker-compose.yml","-f","docker-compose.prod.yml","--env-file",".env.prod")

Write-Host "Building and starting stack (prod override)" -ForegroundColor Cyan
docker compose @compose up -d --build

Write-Host "\nServices:" -ForegroundColor Cyan
docker compose @compose ps

Write-Host "\nTailing nginx logs (Ctrl+C to stop)" -ForegroundColor Cyan
docker compose @compose logs -f nginx

# Helpful commands:
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f api
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f db
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec db psql -U sepid -d servicio_tecnico -f /sql/99_verify.sql

