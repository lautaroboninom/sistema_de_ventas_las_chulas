# Las Chulas Retail - Guía Rápida

## Estado del corte
- Dominio legacy de dominio anterior eliminado del wiring principal.
- API pública activa solo para auth, usuarios/permisos y retail.
- Frontend activo solo con pantallas retail.
- Base de datos definida en `sql/schema.sql` (arranque desde cero).

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
