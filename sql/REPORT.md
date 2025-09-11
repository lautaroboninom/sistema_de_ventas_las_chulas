# Reporte de hallazgos y alineación (Nuevo Sistema de reparación)

Este documento resume el análisis del repo y cómo se plasmaron los resultados en `/sql/`.

## Hallazgos clave y consistencia con el código

- Backend (Django REST) usa intensivamente SQL en `api/service/views.py` y modelos con `managed=False` en `api/service/models.py`. El código es la fuente de verdad.
- `ingreso_events` se usa con columna `ingreso_id` en todas las consultas del backend y en los SQL existentes (`db/init/03_vistas_y_triggers.sql`, `07_alter_*`). Por tanto, se mantiene y consolida `ingreso_id` (no `ticket_id`).
- `quotes` opera solo con `ingreso_id` (bloque de migración en `01_schema.sql` ya elimina `ticket_id` si existía). Triggers/policies sincronizan `ingresos.presupuesto_estado` vía `ingreso_id`.
- Funciones utilizadas por la API:
  - `public.recalc_quote_subtotal(p_ingreso_id int)` — la API la invoca tras cambios en `quote_items`.
  - `public.sync_quote_with_ingreso()` — usada por triggers para reflejar estado de presupuesto y transición a `reparar` si corresponde.
  - `public.log_ingreso_state()` — registra en `ingreso_events` los cambios de estado.
  - RLS helper `public.can_view_ingreso(int)` — referenciada por policies.
- Índices críticos en consultas comunes: sobre `ingresos(estado, fecha_ingreso)`, `ingreso_events(ingreso_id, a_estado, ts DESC, id DESC)`, `quote_items(quote_id)`, `devices(customer_id|marca_id|model_id|numero_serie)`.

## Inconsistencias detectadas (y resolución)

- Duplicidad entre los archivos `db/init` originales (enums, tablas, triggers y policies aparecen en múltiples archivos). Se normalizó en `/sql/` en capas: types → tables → indexes → fkeys → functions → triggers → policies → seed → verify.
- `audit_log` aparece definido en dos archivos (uno con FK opcional a `users`, otro sin); en `/sql/` se crea una sola vez y el FK se agrega de forma idempotente en `04_fkeys.sql` (ON DELETE SET NULL).
- `equipos_derivados` tiene variantes (con/sin default de `fecha_deriv`); se consolidó con `DEFAULT CURRENT_DATE` como en `01_schema.sql` (no es disruptivo para la API y mantiene compatibilidad).
- Contexto inicial indicaba `ingreso_events.ticket_id` como legacy, pero el repo vigente usa `ingreso_id`. Se prioriza el código actual (regla: el código es la fuente de verdad). No se aplican renombres disruptivos.

## Cambios aplicados

- Se creó `/sql/` con 10 archivos transaccionales, idempotentes y ordenados.
- Enums consolidados con `DO $$ ... $$` y `ADD VALUE IF NOT EXISTS`.
- Tablas definidas sin FKs en `02_tables.sql` (PK/UK solamente) y FKs agregadas en `04_fkeys.sql` con detección por catálogo para idempotencia.
- Funciones críticas (`recalc_quote_subtotal`, `sync_quote_with_ingreso`, `log_ingreso_state`, helpers de auditoría y RLS) en `05_functions.sql`.
- Triggers en `06_triggers.sql` (incluye cleanup de guards legacy) en el orden requerido.
- Policies RLS unificadas en `07_policies.sql` acorde a middleware (`app.user_id`, `app.user_role`).
- Seeds mínimos y seguros en `08_seed.sql` (sin secretos; `admin@example.com` como placeholder); catálogo de accesorios ampliado.
- Verificaciones automáticas en `99_verify.sql` para chequear existencia de tablas, FKs, funciones, triggers, policies e índices.

## Sugerencias futuras (no disruptivas)

- Tests/CI: ejecutar `99_verify.sql` en el pipeline tras levantar el contenedor de DB.
- Considerar triggers en `quote_items` para recalcular subtotal automáticamente (la API hoy llama a `recalc_quote_subtotal` explícitamente; un trigger AFTER INSERT/UPDATE/DELETE mantendría la coherencia aún fuera de la API).
- Añadir índices parciales adicionales si el volumen crece (por ejemplo, `ingresos(estado) WHERE estado IN ('reparado','liberado')`).
- Auditar que `service_sheets` (si se agrega en el futuro) se cree con RLS desde `/sql/` y no sólo policies condicionales.
- Mantener `audit` como el único esquema no-`public` y evitar `OWNER TO` para portabilidad entre entornos.

## Supuestos

- PostgreSQL 16, base `servicio_tecnico`, usuario `sepid` (desde Docker compose). `search_path` por defecto.
- La autenticación y permisos de la app dependen de JWT + RLS; se asume que el middleware ya fija `app.user_id` y `app.user_role` por request.
- No se renombra ni elimina nada que rompa contratos actuales (nombres de tablas/columnas, endpoints, JWT, etc.).

