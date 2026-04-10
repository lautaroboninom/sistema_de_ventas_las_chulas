RetailHub - Documentacion

Manual funcional (uso diario)
- [Manual de Usuario RetailHub](docs/MANUAL_USUARIO_RETAILHUB.md)

Indice de documentacion tecnica y operativa
- [Indice en docs](docs/README.md)

Arquitectura rapida
- Backend: `api/service/...` (Django REST)
- Frontend: `web/src/pages/...` (React)
- SQL/Schema: `sql/schema.sql`

Configuracion y despliegue
- Variables de entorno: usar `.env` (local/dev) y `.env.prod` (produccion)
- Modos soportados:
  - `dev`: `docker-compose.yml`
  - `prod`: `docker-compose.prod.yml` (Tailscale + Funnel para webhooks)
- Nginx: `web/deploy/web.nginx.conf` (frontend) y `web/deploy/webhook.nginx.conf` (gateway webhooks)

Integraciones externas (estado)
- ARCA WSAA/WSFEv1: disponible segun configuracion fiscal/certificados.
- Tienda Nube API + webhooks: disponible segun credenciales, OAuth y URL HTTPS publica.
- Si falta configuracion externa, tratar como `No disponible / depende de configuracion externa`.
