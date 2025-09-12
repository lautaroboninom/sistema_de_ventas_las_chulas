# PR: Staging MySQL – Compatibilidad y Verificación

## Contexto
- Proyecto Django + DRF + React/Vite con compatibilidad dual Postgres (prod) y MySQL (staging).
- Mantener contratos: JWT, roles/permisos, endpoints, nombres de tablas/columnas (incluye legacy `ticket_id` en `ingreso_events`).
- RLS aplica solo a Postgres; middleware resuelve JSON para ambos motores.

## Cambios clave
- `_set_audit_user` unificado: PG usa `SET app.user_*`; MySQL no-op.
- Helpers DB: `exec_void`, `q`, `last_insert_id()`.
- INSERT + obtención de ID normalizados en `devices` e `ingresos`:
  - PG: `RETURNING id`.
  - MySQL: `LAST_INSERT_ID()`.
- Portabilidad SQL:
  - Reemplazo de `LATERAL` por `ROW_NUMBER() OVER (...)` + join `rn=1`.
  - Igualdad case-insensitive con `LOWER(col) = LOWER(%s)` (sin ILIKE/collations).
  - Evitar casts específicos de PG en views (sin `::date/::jsonb`).
- Upserts:
  - PG mantiene `ON CONFLICT`.
  - MySQL usa `ON DUPLICATE KEY`/`INSERT IGNORE` según el caso.
- Verificador MySQL (`mysql/99_verify_mysql.sql`):
  - Versión/modos → conteos → FKs (solo orfandad real) → distincts de estados.
- Smokes BD reproducibles (transacción + ROLLBACK).

## Verificación (staging)
- Conteos: users=10, customers=5, marcas=6, models=8, locations=5, devices=18, ingresos=22, quotes=17, quote_items=31, proveedores_externos=1, equipos_derivados=1, ingreso_events=96, handoffs=0, password_reset_tokens=18, audit_log=224.
- FKs: todas 0 (quotes.ingreso_id, quote_items.quote_id, ingreso_events.ticket_id, ingresos.device_id/ubicacion_id/asignado_a/recibido_por, equipos_derivados.ingreso_id/proveedor_id, handoffs.ingreso_id, password_reset_tokens.user_id).
- Distintos: ingresos.estado=[ingresado, diagnosticado, reparar, reparado, entregado, liberado, alquilado]; ingresos.presupuesto_estado=[pendiente, aprobado, presupuestado]; quotes.estado=[pendiente, emitido, aprobado].

## Smokes BD
- Ingreso mínimo → evento `a_estado='ingresado'` OK.
- Quote + 1 item → subtotal/iva/total correctos; al `estado='emitido'`, ingreso `presupuesto_estado='presupuestado'` OK.
- Cambio a `diagnosticado` → evento `de_estado/a_estado` correcto.
- Ejecutados dentro de transacción con ROLLBACK (sin residuos).

## Riesgos y mitigaciones
- ENUMs: mantener correspondencia de estados entre PG/MySQL (ver distincts).
- Fechas: usar `CURRENT_TIMESTAMP`/`CURRENT_DATE` sin casts; middleware y serializadores validan formatos.
- JSON: sin casts en views; middleware adapta `::jsonb`/`CAST AS JSON` fuera de las vistas.

## Cómo reproducir
- Verificador: `make staging-verify` (previo copiar `mysql/99_verify_mysql.sql` al contenedor si fuera necesario).
- Health: `make staging-health`.
- Smokes: usar bloque SQL de smokes (transacción + ROLLBACK) dentro del contenedor MySQL.
