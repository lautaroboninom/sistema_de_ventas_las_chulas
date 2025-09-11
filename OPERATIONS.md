# Operaciones

## Rollback
Si una release falla:
- Identificar la imagen anterior (ej. `docker images` o tags previos del registro si aplica).
- Bajar parcialmente `api` y levantar con la imagen anterior:
  ```bash
  docker compose -f docker-compose.prod.yml pull api # si hay tag previo
  docker compose -f docker-compose.prod.yml up -d api
  ```
- Verificar `/` y `/api/health/`.

## Backups de base de datos
- Crear backup manual:
  ```bash
  deploy/backup_db.sh
  ```
- Copiar al host:
  ```bash
  docker cp sepid-db:/backups/backup_YYYYmmdd_HHMMSS.dump ./db/backups/
  ```
- Restaurar rápido (staging):
  ```bash
  # dentro de un contenedor Postgres limpio
  createdb -U sepid servicio_tecnico
  pg_restore -U sepid -d servicio_tecnico /ruta/al/backup.dump
  ```

## Logs y monitoreo
- Logs centralizados por stdout:
  - Proxy: `docker logs -f sepid-traefik`
  - API: `docker logs -f sepid-api`
  - Web: `docker logs -f sepid-web`
  - DB: `docker logs -f sepid-db`
- (Opcional) Configurar Sentry con `SENTRY_DSN` si ya se usa.

## Rotación de secretos/JWT
- Rotar `DJANGO_SECRET_KEY` y `JWT_SECRET` coordinando expiración de tokens.
- Reiniciar `api` tras actualizar `.env.prod`:
  ```bash
  docker compose -f docker-compose.prod.yml up -d api
  ```

## Actualizaciones sin downtime
- Construir nuevas imágenes: `deploy/build_prod.sh`
- Levantar cambios: `deploy/up_prod.sh`
- Aplicar migraciones: `deploy/migrate.sh`
- Collect static: `deploy/collectstatic.sh`
- Verificaciones: `deploy/verify_prod.sh`

## Checklist de verificación (automatizable)
- DNS resuelve a la IP del host.
- 80 redirige a 443.
- Cert Let’s Encrypt válido (no self-signed).
- `GET /` devuelve el index (200, gzip).
- `GET /api/health` devuelve `{ "ok": true }`.
- `DEBUG=False`, `ALLOWED_HOSTS` correcto.
- Cabeceras seguras presentes: HSTS, X-Frame-Options, etc.
- `collectstatic` ejecutado; assets con cache.
- API responde operaciones básicas con JWT válido.
- DB accesible solo desde red interna; sin puerto expuesto.
- Email SMTP probado con correo de test (sin credenciales en repo).
- Backups `pg_dump` funcionales; restore probado en staging.
- Re-ejecución de `up_prod.sh` idempotente.

