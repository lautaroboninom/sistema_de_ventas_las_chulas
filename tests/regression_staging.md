Staging Regression Checklist (MySQL)

Scope: Validate behavior parity vs Postgres for critical flows.

Preconditions
- Staging stack up: mysql:8.0, api-staging (Django with MySQL), web-staging.
- Schema loaded: mysql/01_schema.sql … 05_triggers.sql, indexes and FKs applied.
- ETL executed (CSV → LOAD DATA LOCAL INFILE) with zero FK/NOT NULL violations.

Data Integrity
- Row counts per table match Postgres export (mysql/99_verify_mysql.sql – section 4).
- FK orphan checks all zero.
- Enums/states: ingresos.estado, ingresos.presupuesto_estado, quotes.estado values within allowed sets.

Auditoría / Eventos
- Al crear un ingreso (POST /api/ingresos/nuevo/): se inserta un evento en ingreso_events con a_estado=‘ingresado’.
- Al cambiar estado (PATCH /api/ingresos/{id}/ …): nuevo evento con de_estado/a_estado correctos.
- ingreso_events.ticket_id referenciando ingresos.id (legacy) permanece; consultas que use ‘ingreso_id’ funcionan (columna generada).

Quotes → Ingresos
- Crear/actualizar presupuesto (POST/PATCH /api/quotes…): sincroniza ingresos.presupuesto_estado por ingreso_id.
- Map ‘emitido’ → ‘presupuestado’. ‘aprobado’ lleva ingresos.estado a ‘reparar’ si venía en (‘ingresado’,’diagnosticado’,’presupuestado’).

Endpoints críticos
- Auth: login, forgot, reset password.
- CRUD de ingresos; pestaña “Diagnóstico y Reparación”.
- PDF de presupuesto y envío por email (si aplica en staging).

SQL Dialect
- Consultas ILIKE reemplazadas por collation/LIKE equivalente o LOWER(col) LIKE LOWER(?).
- RETURNING y ON CONFLICT migrados como en mysql/queries_compat.md.
- JSON en middleware: `CAST(? AS JSON)` o binding nativo.

Performance/Config
- MySQL server variables correctas: STRICT_ALL_TABLES, innodb_strict_mode, sql_require_primary_key, utf8mb4_0900_ai_ci, default-time-zone ‘-03:00’.
- group_concat_max_len aumentado si se usan agregaciones de strings extensas.

RLS
- RLS no existe en MySQL: validado que el middleware/app aplican restricciones de acceso equivalentes (por roles) a nivel de consultas/endpoints.

