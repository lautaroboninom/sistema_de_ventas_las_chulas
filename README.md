Las Chulas Retail - Documentación

- Manual del sistema: ver `docs/README.md`.

Archivos de interés
- Backend: `api/service/...` (Django REST).
- Frontend: `web/src/pages/...` (React).
- SQL/Schema: `sql/schema.sql`.

Configuración y despliegue
- Variables de entorno: usar solo `.env` (local/dev) y `.env.prod` (producción).
- Docker Compose y Nginx: `docker-compose*.yml`, `web/deploy/web.nginx.conf` (HTTP) y `web/deploy/web.nginx.tls.conf` (TLS).
