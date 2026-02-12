"""
Instala/actualiza el esquema de auditoría (audit.change_log y triggers)
en la base PostgreSQL actual. Idempotente.

Usa las mismas variables que el resto de scripts para conectar:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""

from __future__ import annotations
import os
import psycopg

DDL = r'''
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS audit.change_log (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id      INTEGER NULL,
  user_role    TEXT NULL,
  table_name   TEXT NOT NULL,
  record_id    INTEGER NOT NULL,
  column_name  TEXT NOT NULL,
  old_value    TEXT NULL,
  new_value    TEXT NULL,
  ingreso_id   INTEGER NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_change_log_ts ON audit.change_log(ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_change_log_ingreso ON audit.change_log(ingreso_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_change_log_table ON audit.change_log(table_name, record_id, ts DESC);

CREATE OR REPLACE FUNCTION audit.log_row_change()
RETURNS TRIGGER AS $$
DECLARE
  jold jsonb;
  jnew jsonb;
  k text;
  oval text;
  nval text;
  rec_id integer;
  tname text := TG_TABLE_NAME;
  _user_id text := current_setting('app.user_id', true);
  _user_role text := current_setting('app.user_role', true);
  _ingreso_id text := current_setting('app.ingreso_id', true);
  v_ingreso_id integer;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    jold := to_jsonb(OLD);
    jnew := to_jsonb(NEW);
    rec_id := COALESCE((to_jsonb(NEW)->>'id')::int, (to_jsonb(OLD)->>'id')::int);
  ELSIF TG_OP = 'INSERT' THEN
    jold := '{}'::jsonb;
    jnew := to_jsonb(NEW);
    rec_id := (to_jsonb(NEW)->>'id')::int;
  ELSE
    jold := to_jsonb(OLD);
    jnew := '{}'::jsonb;
    rec_id := (to_jsonb(OLD)->>'id')::int;
  END IF;

  v_ingreso_id := NULL;
  IF tname = 'ingresos' THEN
    v_ingreso_id := rec_id;
  ELSIF tname = 'ingreso_accesorios' THEN
    IF TG_OP = 'DELETE' THEN
      v_ingreso_id := (to_jsonb(OLD)->>'ingreso_id')::int;
    ELSE
      v_ingreso_id := (to_jsonb(NEW)->>'ingreso_id')::int;
    END IF;
  ELSE
    IF COALESCE(_ingreso_id,'') <> '' THEN
      v_ingreso_id := NULLIF(_ingreso_id,'')::int;
    END IF;
  END IF;

  FOR k IN
    SELECT key FROM (
      SELECT jsonb_object_keys(jold) AS key
      UNION
      SELECT jsonb_object_keys(jnew) AS key
    ) s
  LOOP
    IF k IN ('updated_at','created_at') THEN CONTINUE; END IF;
    oval := jold->>k;
    nval := jnew->>k;
    IF (oval IS DISTINCT FROM nval) THEN
      INSERT INTO audit.change_log(ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value, ingreso_id)
      VALUES (now(), NULLIF(_user_id,'')::int, NULLIF(_user_role,''), tname, rec_id, k, oval, nval, v_ingreso_id);
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingresos') THEN
    CREATE TRIGGER trg_audit_ingresos AFTER INSERT OR UPDATE OR DELETE ON ingresos
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_devices') THEN
    CREATE TRIGGER trg_audit_devices AFTER INSERT OR UPDATE OR DELETE ON devices
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingreso_accesorios') THEN
    CREATE TRIGGER trg_audit_ingreso_accesorios AFTER INSERT OR UPDATE OR DELETE ON ingreso_accesorios
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_quotes') THEN
    CREATE TRIGGER trg_audit_quotes AFTER INSERT OR UPDATE OR DELETE ON quotes
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_quote_items') THEN
    CREATE TRIGGER trg_audit_quote_items AFTER INSERT OR UPDATE OR DELETE ON quote_items
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  -- Catálogos y usuarios
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_marcas') THEN
    CREATE TRIGGER trg_audit_marcas AFTER INSERT OR UPDATE OR DELETE ON marcas
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_models') THEN
    CREATE TRIGGER trg_audit_models AFTER INSERT OR UPDATE OR DELETE ON models
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_customers') THEN
    CREATE TRIGGER trg_audit_customers AFTER INSERT OR UPDATE OR DELETE ON customers
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_users') THEN
    CREATE TRIGGER trg_audit_users AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_proveedores_externos') THEN
    CREATE TRIGGER trg_audit_proveedores_externos AFTER INSERT OR UPDATE OR DELETE ON proveedores_externos
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
END $$;
'''


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def main() -> int:
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
    print("Audit schema installed/updated.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
