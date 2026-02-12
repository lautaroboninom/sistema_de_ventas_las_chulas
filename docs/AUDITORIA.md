Auditoría de Cambios y Eventos

Resumen
- change_log (PostgreSQL): difs por columna capturadas por triggers. Fuente principal del historial.
- ingreso_events: hitos de estado del ingreso (línea de tiempo del proceso). Se usa para métricas y como fallback en entornos sin change_log.
- audit_log: trazas de requests HTTP (método, ruta, usuario y body). Útil para depurar, no se muestra por defecto en la Hoja de Servicio.

Alcance auditado por change_log
- Tablas con trigger activo:
  - ingresos, devices, ingreso_accesorios, quotes, quote_items
  - marcas, models, customers, users, proveedores_externos
    - Se agregan con `sql/ops/add_audit_triggers_catalogs.sql` y `scripts/install_audit_pg.py`.

Historial de Hoja de Servicio (ServiceSheet)
- Endpoint: `GET /api/ingresos/:id/historial/`
- Comportamiento por defecto:
  - En PostgreSQL: solo `change_log` (sin `audit_log`) para evitar redundancia.
  - En otros motores: `ingreso_events` y, opcionalmente, `audit_log` (ver parámetro abajo).
- Parámetros opcionales:
  - `include_audit=1|true`: añade una línea por request de `audit_log` (resumen, sin expandir JSON por clave).

Cuándo usar cada fuente
- `change_log`: ver qué campo cambió, antes/después y quién lo hizo.
- `ingreso_events`: analizar tiempos y estados del proceso (diagnosticado, reparado, liberado, etc.).
- `audit_log`: depurar llamadas HTTP (qué endpoint y payload se enviaron).

Operación/Deploy
- Producción: ejecutar `scripts/install_audit_pg.py` o aplicar `sql/ops/add_audit_triggers_catalogs.sql` para activar triggers en catálogos/usuarios.
- Rollback: `DROP TRIGGER ... ON <tabla>` (mantiene `audit.change_log` y datos existentes).

Notas
- La UI de ServiceSheet no muestra `audit_log` por defecto para mantener el historial legible.
- `include_audit` está pensado como toggle de diagnóstico o para una vista separada de auditoría.

