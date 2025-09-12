Cutover Plan (Postgres → MySQL) — Staging First

Scope
- Move backend API to MySQL 8.0 only after staging parity achieved. Production remains on Postgres until all checks pass.

Pre-cutover
- Full backup of Postgres (logical dump) and snapshot of staging MySQL volume.
- Freeze writes in app (maintenance window) or route traffic to read-only endpoints.

Steps
1) Staging validation complete (tests/regression_staging.md all green; mysql/99_verify_mysql.sql OK).
2) Final ETL:
   - Export from Postgres (etl/export_pg.sh)
   - Truncate MySQL tables (in FK-safe order) or load with REPLACE semantics; import with etl/import_mysql.sh
   - Re-check FK and counts.
3) Switch API configuration:
   - Update environment to use DJANGO_SETTINGS_MODULE=app.settings_staging_mysql (for staging).
   - Confirm health/readiness.
4) Shadow traffic (optional):
   - Replay a subset of read requests to MySQL and compare responses.

Rollback
- If any check fails post-switch:
  - Revert API to Postgres DATABASES config.
  - Restore any data written during the failed window from audit logs/queues or reconcile manually.

Notes
- RLS is handled at app layer in MySQL. Ensure no sensitive endpoints rely solely on DB policies.
- Timezone fixed at -03:00 on DB server; app uses America/Argentina/Buenos_Aires (USE_TZ=True).
- No renames of legacy columns (ingreso_events.ticket_id) in this phase.

