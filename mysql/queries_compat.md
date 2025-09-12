
MySQL Compatibility Notes (Backend SQL)

Scope: Django/DRF raw SQL in `api/service/*.py` and schema SQL in `db/init/*.sql` mapped for MySQL 8.0.

General Rules

- ILIKE: prefer collation `utf8mb4_0900_ai_ci` (case/accent-insensitive). If needed per-query: `... COLLATE utf8mb4_0900_ai_ci`. Fallback: `LOWER(col) LIKE LOWER(?)` (can defeat index if not collated).
- DISTINCT ON: use window functions: `ROW_NUMBER() OVER(PARTITION BY ... ORDER BY ...) = 1` in a subquery.
- string_agg/array_agg: use `GROUP_CONCAT(expr ORDER BY ... SEPARATOR ',')`. Consider increasing `group_concat_max_len` if needed.
- ON CONFLICT ... DO UPDATE: use `INSERT ... ON DUPLICATE KEY UPDATE ...`.
- RETURNING: use `LAST_INSERT_ID()` or a subsequent `SELECT`.
- jsonb: use MySQL `JSON` and functions `JSON_EXTRACT`, `JSON_SET`, etc. Use parameter binding for JSON values; or `CAST(? AS JSON)`.
- LATERAL: MySQL supports `LATERAL` (8.0.14+) via `LEFT JOIN LATERAL (...)`. Alternative: correlated subquery with `ORDER BY ... LIMIT 1`.
- Casts `::type`: replace with `CAST(... AS ...)` or adjust expressions.

Concrete occurrences (file:line)

- api/service/views.py
  - ILIKE: 723, 770, 846, 1654, 1700, 1743, 1785, 1821, 1829, 2273.
    - Patch: replace `... ILIKE 'taller'` with `... LIKE 'taller' COLLATE utf8mb4_0900_ai_ci`.
    - Patch for search: `LOWER(c.razon_social) LIKE LOWER(%s)` → `(c.razon_social COLLATE utf8mb4_0900_ai_ci) LIKE %s` with `%foo%` prepared already in lower-case.
  - RETURNING (121, 959, 1020, 1210, 1260):
    - Example: line 121 `INSERT ... ON CONFLICT ... RETURNING id` → two-step:
      1) `INSERT INTO quotes(ingreso_id) VALUES (%s) ON DUPLICATE KEY UPDATE ingreso_id=VALUES(ingreso_id)`
      2) `SELECT id FROM quotes WHERE ingreso_id=%s` (or `SELECT LAST_INSERT_ID()` if using surrogate key insert).
  - ON CONFLICT (1302, 1487, 1588, 1616):
    - Convert to `INSERT ... ON DUPLICATE KEY UPDATE ...` (ensure unique keys exist: e.g., quotes.ingreso_id, marcas.nombre, (marca_id, nombre) for models, proveedores_externos.nombre).
  - LATERAL (1735, 1777):
    - Use `LEFT JOIN LATERAL (SELECT e.ts ... WHERE e.ticket_id = t.id AND e.a_estado = 'reparado' ORDER BY e.ts DESC, e.id DESC LIMIT 1) ev ON TRUE`.
    - Alternative: correlated subquery: `LEFT JOIN (SELECT MAX(e.ts) AS fecha_reparado FROM ingreso_events e WHERE e.ticket_id = t.id AND e.a_estado='reparado') ev ON TRUE`.
  - CASTs `::text`, `::timestamp`: replace with `CAST(... AS CHAR)` / `CAST(... AS DATETIME)` or restructure.

- api/service/middleware.py:86 `%s::jsonb`
  - Patch: `... VALUES (..., CAST(? AS JSON))` or pass Python dict and rely on driver binding to JSON if using mysqlclient.

- db/init/06_users_perms.sql: ARRAY_AGG head/tail
  - Replace `(ARRAY_AGG(... ORDER BY ...))[1]` with window function: `ROW_NUMBER()` and filter `=1`, or `MAX(...) KEEP DENSE_RANK FIRST`-like with window emulation.

Index/Collation Guidance

- Text columns used in LIKE/ILIKE filters (e.g., `locations.nombre`, `customers.razon_social`, `devices.numero_serie`, `marcas.nombre`, `models.nombre`) should use collation `utf8mb4_0900_ai_ci` to preserve case/accent-insensitive behavior with index support. If column-level collation diverges, use explicit `COLLATE` in queries.

LATERAL patterns

- Top-1 per group pattern:
  - Using window: `SELECT * FROM (SELECT e.*, ROW_NUMBER() OVER (PARTITION BY e.ticket_id ORDER BY e.ts DESC, e.id DESC) rn FROM ingreso_events e WHERE e.a_estado='reparado') x WHERE x.rn=1`.
  - Using LATERAL: `LEFT JOIN LATERAL (SELECT ... ORDER BY ... LIMIT 1) ev ON TRUE`.
- Upsert + id (patrón recomendado):
  - Ejemplo `quotes(ingreso_id)` único:
    - `INSERT INTO quotes(ingreso_id) VALUES (?)
       ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);`
    - `SELECT LAST_INSERT_ID() AS id;`
  - Garantiza obtener `id` tanto en insert nuevo como en colisión por único.
