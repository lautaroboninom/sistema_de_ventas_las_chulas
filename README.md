Sistema de Reparaciones — Documentación

- Manual del sistema: ver `docs/README.md`.
- Operativa de remitos y presupuestos: ver `docs/operativa_remitos_presupuestos.md`.

Archivos de interés
- Backend: `api/service/...` (Django REST: vistas, URLs, PDFs).
- Frontend: `web/src/pages/...` (React: pantallas y flujos).
- SQL/Schema: `sql/schema.sql`.

Configuración y despliegue
- Variables de entorno: copiar `.env.example` a `.env` y `.env.prod.example` a `.env.prod` (y, si aplica, `.env.prod.internet.example` a `.env.prod.internet`).
- Docker Compose y Nginx: `docker-compose*.yml`, `web/deploy/web.nginx.conf` (HTTP) y `web/deploy/web.nginx.tls.conf` (TLS).
