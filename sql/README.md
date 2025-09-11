# SQL Bootstrap for Nuevo Sistema de reparación

This folder contains a normalized, idempotent, and transactional setup for the PostgreSQL schema used by the project. Files are split by concern and safe to re-run in order.

Target: PostgreSQL 16, database `servicio_tecnico`, user `sepid` (as in the Docker compose).

## Files and order

1. `00_extensions.sql` — Extensions (none required; placeholder for portability)
2. `01_types.sql` — Enums and custom types (e.g., `ticket_state`, `quote_state`, etc.)
3. `02_tables.sql` — Tables only (PK/UK, no FKs yet). Timestamps are `timestamptz`.
4. `03_indexes.sql` — Non-PK indexes to speed up UI/API queries.
5. `04_fkeys.sql` — Foreign keys only, added idempotently.
6. `05_functions.sql` — Functions (PL/pgSQL and SQL) used by triggers/RLS.
7. `06_triggers.sql` — Triggers in dependency order.
8. `07_policies.sql` — RLS policies (leveraging `app.user_id` and `app.user_role`).
9. `08_seed.sql` — Minimal, safe seed data. No secrets.
10. `99_verify.sql` — Automated checks to confirm setup.

Every file wraps changes in `BEGIN/COMMIT` and is re-executable without errors.

## How to run (Docker)

Use the `db` service from `docker-compose.yml`:

```
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/00_extensions.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/01_types.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/02_tables.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/03_indexes.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/04_fkeys.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/05_functions.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/06_triggers.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/07_policies.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/08_seed.sql
docker compose exec db psql -U sepid -d servicio_tecnico -f /sql/99_verify.sql
```

Adjust DB name/user if your `.env` differs.

Note: ensure the folder is available inside the container. If not already mounted, add this volume to the `db` service in `docker-compose.yml`:

```
    volumes:
      - ./sql:/sql:ro
```

## Assumptions and session context

- Schema uses `public` (and `audit` for audit helpers). `search_path` is default.
- Backend sets GUCs per request via middleware:
  - `SET LOCAL app.user_id = '...'`
  - `SET LOCAL app.user_role = '...'`
  - Optionally: `SET LOCAL app.ingreso_id = '...'` for audit correlation
- Authentication: custom JWT; permissions aligned with RLS policies.

## Key domain notes

- `ingreso_events` uses `ingreso_id` consistently throughout DB/queries.
- Quotes sync `ingresos.presupuesto_estado` using `ingreso_id` (not legacy `ticket_id`).
- Triggers `trg_ingreso_state_log_insert` and `trg_ingreso_state_log_update` call `log_ingreso_state()`.

## DoD checklist

- You can provision from scratch with these 10 files in order without errors.
- Re-running is safe (all scripts are idempotent and transactional).
- `99_verify.sql` confirms presence of tables, FKs, functions, triggers, policies, and critical indexes.
- Current backend (Django REST) and frontend (React) operate unchanged on a DB created by these scripts.
