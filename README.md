Las Chulas Retail - Documentación

- Manual del sistema: ver `docs/README.md`.

Archivos de interés
- Backend: `api/service/...` (Django REST).
- Frontend: `web/src/pages/...` (React).
- SQL/Schema: `sql/schema.sql`.

Configuración y despliegue
- Variables de entorno: usar solo `.env` (local/dev) y `.env.prod` (producción).
- Modos soportados:
  - `dev`: `docker-compose.yml`
  - `prod`: `docker-compose.prod.yml` (Tailscale + Funnel para webhooks)
- Nginx: `web/deploy/web.nginx.conf` (frontend) y `web/deploy/webhook.nginx.conf` (gateway webhooks).

Publicación Tailscale/Funnel (prod)
- El valor `PUBLIC_HOST` en `.env.prod` solo configura hosts/orígenes en Django; no publica la URL por sí solo.
- Para publicar la URL:
  - `tailscale serve --bg 80`
  - `tailscale funnel --bg 80`
  - verificar: `tailscale funnel status`
- Para desactivar exposición pública:
  - `tailscale funnel --https=443 off`

Seguridad de despliegue (Fase 1)
- Admin privado (Tailscale Serve): exponer `127.0.0.1:80`.
- Webhooks públicos (Tienda Nube/Funnel): exponer solo `127.0.0.1:8080` (`webhook_gateway`).
- Producción usa cache compartida Redis para lockout/rate-limit (`REDIS_URL`).
- Rotación operativa de secretos: ver `docs/SEGURIDAD_ROTACION_SECRETOS.md`.
- Usar `.env.prod.example` como base y generar `.env.prod` local antes de deploy (rotación con `deploy/rotate_secrets.ps1`).
