# Las Chulas Retail - Guía Rápida

## Estado del corte
- Dominio legacy de dominio anterior eliminado del wiring principal.
- API pública activa solo para auth, usuarios/permisos y retail.
- Frontend activo solo con pantallas retail.
- Base de datos definida en `sql/schema.sql` (arranque desde cero).
- Deploy con 2 modos: `dev` (`docker-compose.yml`) y `prod` (`docker-compose.prod.yml`).
- Producción requiere además `tailscale serve/funnel` para publicar `https://<host>.ts.net`.

## Rutas frontend
- `/pos`
- `/productos`
- `/compras`
- `/ventas`
- `/reportes`
- `/online`
- `/config`
- `/config/paginas`
- `/login`

## Endpoints backend principales
- Auth: `/api/auth/*`
- Usuarios/permisos: `/api/usuarios/*`, `/api/permisos/catalogo/`
- Retail: `/api/retail/*`

## Configuración de páginas
- API: `GET/PUT /api/retail/config/page-settings/`
- UI: `/config/paginas`
- Permite editar:
  - nombre de app y subtítulo
  - labels del sidebar
  - títulos por página
  - ruta inicial por defecto

## Integraciones
- ARCA WSAA/WSFEv1: estado fiscal por venta (`pending`, `authorized`, `rejected`, `retry`, `manual_review`, `not_required`).
- Tienda Nube: sync catálogo/stock, webhooks `orden-pagada` y `orden-cancelada`, idempotencia por evento.

## Pendientes funcionales/externos
Ver `docs/PENDIENTES.md`.
Para enlace y migración de Tienda Nube: `docs/CHECKLIST_TIENDANUBE_PASO_A_PASO.md`.
Para instalacion automatizada en PC cliente (Windows): `docs/INSTALACION_CLIENTE_WINDOWS.md`.

## Seguridad operativa
- Rotacion de secretos y checklist post-cambio: `docs/SEGURIDAD_ROTACION_SECRETOS.md`.
- `.env.prod.example` es la plantilla versionada; `.env.prod` local valida secretos fuertes en `settings_prod`.
