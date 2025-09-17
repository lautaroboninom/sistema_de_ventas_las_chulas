$ErrorActionPreference = "Stop"

# Variables
# Usa .env.prod para despliegue LAN (sin internet).
# Para publicar en internet, ejecuta docker compose con --env-file .env.prod.internet.
$compose = @("-f","docker-compose.yml","-f","docker-compose.prod.yml","--env-file",".env.prod")

Write-Host "Building and starting stack (prod override)" -ForegroundColor Cyan
docker compose @compose up -d --build

Write-Host "`nServices:" -ForegroundColor Cyan
docker compose @compose ps

Write-Host "`nTailing reverse-proxy (Traefik) logs (Ctrl+C to stop)" -ForegroundColor Cyan
docker compose @compose logs -f reverse-proxy

# Helpful commands:
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f reverse-proxy
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f api
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f mysql
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT NOW()"'
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod.internet up -d --build
# docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod.internet logs -f reverse-proxy
