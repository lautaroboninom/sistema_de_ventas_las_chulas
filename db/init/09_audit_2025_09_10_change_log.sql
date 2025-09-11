-- Audit logging for critical edits (clientes / equipo / NS / propietario)
-- Keeps an append-only change_log with per-field history.

BEGIN;

-- Schema to keep audit objects grouped
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.change_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  user_id      text,
  user_role    text,
  ingreso_id   int,              -- set from current_setting('app.ingreso_id') when available
  table_name   text NOT NULL,
  record_id    int  NOT NULL,
  column_name  text NOT NULL,
  old_value    text,
  new_value    text
);

CREATE INDEX IF NOT EXISTS idx_change_log_ingreso ON audit.change_log(ingreso_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_table   ON audit.change_log(table_name, record_id);

-- Guards: make the log append-only at DB level
CREATE OR REPLACE FUNCTION audit.prevent_change_log_mod()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit.change_log is append-only';
  RETURN NULL;
END$$;

DROP TRIGGER IF EXISTS trg_change_log_no_update ON audit.change_log;
CREATE TRIGGER trg_change_log_no_update
  BEFORE UPDATE ON audit.change_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_change_log_mod();

DROP TRIGGER IF EXISTS trg_change_log_no_delete ON audit.change_log;
CREATE TRIGGER trg_change_log_no_delete
  BEFORE DELETE ON audit.change_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_change_log_mod();

-- Helper to pull session context safely
CREATE OR REPLACE FUNCTION audit._ctx_user_id() RETURNS text LANGUAGE sql AS $$
  SELECT current_setting('app.user_id', true)
$$;
CREATE OR REPLACE FUNCTION audit._ctx_user_role() RETURNS text LANGUAGE sql AS $$
  SELECT current_setting('app.user_role', true)
$$;
CREATE OR REPLACE FUNCTION audit._ctx_ingreso_id() RETURNS integer LANGUAGE sql AS $$
  SELECT NULLIF(current_setting('app.ingreso_id', true), '')::int
$$;

-- Customers: log razon_social, cod_empresa, telefono
CREATE OR REPLACE FUNCTION audit.log_customer_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_ingreso int;
  v_uid text;
  v_role text;
BEGIN
  v_ingreso := audit._ctx_ingreso_id();
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();

  IF TG_OP = 'UPDATE' THEN
    IF NEW.razon_social IS DISTINCT FROM OLD.razon_social THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'razon_social', OLD.razon_social::text, NEW.razon_social::text);
    END IF;
    IF NEW.cod_empresa IS DISTINCT FROM OLD.cod_empresa THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'cod_empresa', OLD.cod_empresa::text, NEW.cod_empresa::text);
    END IF;
    IF NEW.telefono IS DISTINCT FROM OLD.telefono THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'telefono', OLD.telefono::text, NEW.telefono::text);
    END IF;
  END IF;
  RETURN NEW;
END$$;

-- Devices: log numero_serie, n_de_control
CREATE OR REPLACE FUNCTION audit.log_device_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_ingreso int;
  v_uid text;
  v_role text;
BEGIN
  v_ingreso := audit._ctx_ingreso_id();
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();

  IF TG_OP = 'UPDATE' THEN
    IF NEW.numero_serie IS DISTINCT FROM OLD.numero_serie THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'devices', OLD.id, 'numero_serie', OLD.numero_serie::text, NEW.numero_serie::text);
    END IF;
    IF NEW.n_de_control IS DISTINCT FROM OLD.n_de_control THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'devices', OLD.id, 'n_de_control', OLD.n_de_control::text, NEW.n_de_control::text);
    END IF;
  END IF;
  RETURN NEW;
END$$;

-- Ingresos: log propietario_* (datos del que trajo el equipo)
CREATE OR REPLACE FUNCTION audit.log_ingreso_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_ingreso int;
  v_uid text;
  v_role text;
BEGIN
  v_ingreso := COALESCE(audit._ctx_ingreso_id(), NEW.id);
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();

  IF TG_OP = 'UPDATE' THEN
    IF NEW.propietario_nombre IS DISTINCT FROM OLD.propietario_nombre THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_nombre', OLD.propietario_nombre::text, NEW.propietario_nombre::text);
    END IF;
    IF NEW.propietario_contacto IS DISTINCT FROM OLD.propietario_contacto THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_contacto', OLD.propietario_contacto::text, NEW.propietario_contacto::text);
    END IF;
    IF NEW.propietario_doc IS DISTINCT FROM OLD.propietario_doc THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_doc', OLD.propietario_doc::text, NEW.propietario_doc::text);
    END IF;
    -- Diagnóstico y trabajos realizados
    IF NEW.descripcion_problema IS DISTINCT FROM OLD.descripcion_problema THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'descripcion_problema', OLD.descripcion_problema::text, NEW.descripcion_problema::text);
    END IF;
    IF NEW.trabajos_realizados IS DISTINCT FROM OLD.trabajos_realizados THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'trabajos_realizados', OLD.trabajos_realizados::text, NEW.trabajos_realizados::text);
    END IF;
  END IF;
  RETURN NEW;
END$$;

-- Triggers
DROP TRIGGER IF EXISTS trg_audit_customers ON public.customers;
CREATE TRIGGER trg_audit_customers
  AFTER UPDATE OF razon_social, cod_empresa, telefono ON public.customers
  FOR EACH ROW EXECUTE FUNCTION audit.log_customer_change();

DROP TRIGGER IF EXISTS trg_audit_devices ON public.devices;
CREATE TRIGGER trg_audit_devices
  AFTER UPDATE OF numero_serie, n_de_control ON public.devices
  FOR EACH ROW EXECUTE FUNCTION audit.log_device_change();

DROP TRIGGER IF EXISTS trg_audit_ingresos ON public.ingresos;
CREATE TRIGGER trg_audit_ingresos
  AFTER UPDATE OF propietario_nombre, propietario_contacto, propietario_doc,
                  descripcion_problema, trabajos_realizados
  ON public.ingresos
  FOR EACH ROW EXECUTE FUNCTION audit.log_ingreso_change();

-- HTTP-level activity log (app middleware)
CREATE TABLE IF NOT EXISTS public.audit_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  user_id      int,
  role         text,
  method       text,
  path         text,
  ip           text,
  user_agent   text,
  status_code  int,
  body         jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_log_ts    ON public.audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_path  ON public.audit_log(path);
CREATE INDEX IF NOT EXISTS idx_audit_log_user  ON public.audit_log(user_id);

-- Protect audit_log as append-only too
CREATE OR REPLACE FUNCTION audit.prevent_audit_log_mod()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
  RETURN NULL;
END$$;

DROP TRIGGER IF EXISTS trg_audit_log_no_update ON public.audit_log;
CREATE TRIGGER trg_audit_log_no_update
  BEFORE UPDATE ON public.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_audit_log_mod();

DROP TRIGGER IF EXISTS trg_audit_log_no_delete ON public.audit_log;
CREATE TRIGGER trg_audit_log_no_delete
  BEFORE DELETE ON public.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_audit_log_mod();

COMMIT;
