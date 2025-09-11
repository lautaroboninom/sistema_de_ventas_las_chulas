# Producción: reparaciones.sepid.com.ar

Objetivo: despliegue reproducible, seguro (HTTPS), con Traefik como proxy, API Django detrás de Gunicorn, frontend Vite servido por nginx, y Postgres sin exposición pública.

## Requisitos previos
- DNS: `A/AAAA` de `reparaciones.sepid.com.ar` apuntando a la IP del host donde corre Traefik.
- Docker + Docker Compose instalados en el host.
- Archivo `.env.prod` (no subir credenciales reales al repo). Usar `.env.prod.example` como plantilla.

## Topología
- `reverse-proxy` (Traefik): único servicio con puertos `80/443` publicados.
- `web` (nginx:alpine): sirve estáticos del build de Vite y `/static/` de Django.
- `api` (Django + Gunicorn): sin puertos publicados; unido a Traefik por red `proxy`.
- `db` (Postgres 16): sin puertos publicados; red interna `backend`.

## Variables de entorno (solo PROD)
Crear `.env.prod` a partir de `.env.prod.example` y completar:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS=reparaciones.sepid.com.ar`
- `ALLOWED_ORIGINS=https://reparaciones.sepid.com.ar`
- `POSTGRES_USER=sepid`, `POSTGRES_DB=servicio_tecnico`, `POSTGRES_PASSWORD=<secreto>`
- `EMAIL_*` si SMTP real
- `TZ=America/Argentina/Buenos_Aires`
- (opcional) `VITE_API_URL=https://reparaciones.sepid.com.ar` (el front usa mismo origen por defecto)

## Certificados TLS (Let’s Encrypt)
Traefik resuelve y renueva con ACME HTTP-01 automáticamente. El almacenamiento está en `deploy/traefik/acme.json`. El script `deploy/up_prod.sh` crea el archivo y aplica `chmod 600`.

## Comandos de despliegue (cero downtime recomendado)
```bash
# 1) Build imágenes
deploy/build_prod.sh

# 2) Levantar stack (proxy, db, api, web)
deploy/up_prod.sh

# 3) Migraciones
deploy/migrate.sh

# 4) Collect static (Django admin, etc.)
deploy/collectstatic.sh

# 5) Pruebas de humo
deploy/healthcheck.sh  # ó deploy/verify_prod.sh para checklist extendido
```

## Redes y seguridad
- Solo `reverse-proxy` publica 80/443.
- `db` corre en red `backend` interna (no accesible desde fuera).
- CORS y CSRF: mínimos necesarios al dominio de prod.
- Cabeceras seguras aplicadas por Traefik: HSTS, X-Frame-Options (DENY), X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- Rate limit básico y límite de tamaño de request aplicados al router `/api`.

## Django en producción
- Módulo: `app.settings_prod` (ver `api/app/settings_prod.py`).
- `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')` activo.
- `STATIC_ROOT=/app/staticfiles`, compartido con `web` vía volumen `staticfiles`.
- Logging a stdout (nivel INFO).
- Zona horaria: `America/Argentina/Buenos_Aires`.

## Frontend Vite
- Build en `web/Dockerfile.prod` (multi-stage: Node → nginx:alpine).
- `deploy/web.nginx.conf` habilita cache de assets, gzip y SPA fallback.
- No sirve `/api/` (lo enruta Traefik al servicio `api`).

## Healthchecks
- `/` debe devolver el index del frontend (200, gzip).
- `/api/health/` devuelve `{"ok": true}`.

## Notas
- No subir `.env.prod` real al repo. Mantener secretos fuera (por ejemplo, en un vault o en el host). 
- Si no se usa QUOTES_HOST_DIR, eliminar o ajustar el bind correspondiente en `docker-compose.prod.yml`.

