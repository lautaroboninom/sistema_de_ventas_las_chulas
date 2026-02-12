Sistema de Reparaciones - Documentacion

- Manual del sistema: ver `docs/README.md`.

Archivos de interes
- Backend: `api/service/...` (Django REST: vistas, URLs, PDFs).
- Frontend: `web/src/pages/...` (React: pantallas y flujos).
- SQL/Schema: `sql/schema.sql`.

Configuracion y despliegue
- Variables de entorno: `.env`, `.env.prod`, `.env.prod.internet`.
- Docker Compose: `docker-compose*.yml`.
- Precheck VM internet: `deploy/vm_internet_precheck.ps1`.
- Up VM internet: `deploy/vm_internet_up.ps1`.
