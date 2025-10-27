-- schema/postgres.sql
-- Esquema consolidado para PostgreSQL (12+)
-- Unifica DDL, índices, vistas y triggers necesarios para la app.
-- Objetivo: base “prolija” y mínima sin parches adicionales.

SET TIME ZONE 'America/Argentina/Buenos_Aires';
CREATE EXTENSION IF NOT EXISTS citext;

-- =============================
-- Tipos enumerados (dominios)
-- =============================
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_state') THEN
    CREATE TYPE ticket_state AS ENUM (
      'ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'motivo_ingreso') THEN
    CREATE TYPE motivo_ingreso AS ENUM (
      'reparación','service preventivo','baja alquiler','reparación alquiler','urgente control','devolución demo','otros'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'disposicion_type') THEN
    CREATE TYPE disposicion_type AS ENUM ('normal','para_repuesto');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'quote_estado') THEN
    CREATE TYPE quote_estado AS ENUM ('pendiente','emitido','aprobado','rechazado','presupuestado','no_aplica');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'quote_item_tipo') THEN
    CREATE TYPE quote_item_tipo AS ENUM ('repuesto','mano_obra','servicio');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deriv_estado') THEN
    CREATE TYPE deriv_estado AS ENUM ('derivado','en_servicio','devuelto','entregado_cliente');
  END IF;
END $$;

-- =============================
-- Funciones utilitarias / triggers
-- =============================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_log_no_update()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sync_quote_with_ingreso()
RETURNS TRIGGER AS $$
DECLARE
  v_cur_estado ticket_state;
  v_new_estado quote_estado;
BEGIN
  v_new_estado := NEW.estado;
  SELECT estado INTO v_cur_estado FROM ingresos WHERE id = NEW.ingreso_id;
  UPDATE ingresos
     SET presupuesto_estado = (
            CASE v_new_estado
              WHEN 'emitido' THEN 'presupuestado'::quote_estado
              WHEN 'presupuestado' THEN 'presupuestado'::quote_estado
              WHEN 'aprobado' THEN 'aprobado'::quote_estado
              WHEN 'rechazado' THEN 'rechazado'::quote_estado
              WHEN 'no_aplica' THEN 'no_aplica'::quote_estado
              ELSE 'pendiente'::quote_estado
            END
         ),
         estado = (
            CASE
              WHEN v_new_estado = 'aprobado' AND v_cur_estado IN ('ingresado','diagnosticado','presupuestado') THEN 'reparar'::ticket_state
              ELSE v_cur_estado
            END
         )
   WHERE id = NEW.ingreso_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================
-- Tablas base
-- =============================
CREATE TABLE IF NOT EXISTS users (
  id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre           TEXT        NOT NULL,
  email            CITEXT NOT NULL UNIQUE,
  hash_pw          TEXT,
  rol              TEXT NOT NULL,
  activo           BOOLEAN     NOT NULL DEFAULT TRUE,
  creado_en        TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  perm_ingresar    BOOLEAN     NOT NULL DEFAULT FALSE,
  CONSTRAINT users_perm_ingresar_tecnico_chk
    CHECK (NOT (rol = 'tecnico' AND perm_ingresar = TRUE))
);

CREATE TABLE IF NOT EXISTS marcas (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre      TEXT NOT NULL,
  tecnico_id  INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT uq_marcas_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS models (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  marca_id    INTEGER NOT NULL REFERENCES marcas(id) ON DELETE RESTRICT,
  nombre      TEXT NOT NULL,
  tecnico_id  INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  tipo_equipo TEXT NULL,
  variante    TEXT NULL,
  CONSTRAINT uq_models_marca_nombre UNIQUE (marca_id, nombre)
);

CREATE TABLE IF NOT EXISTS locations (
  id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre  TEXT NOT NULL UNIQUE
);

-- Seed mínimo indispensable
INSERT INTO locations(nombre) VALUES
  ('Taller'),
  ('Sarmiento'),
  ('Estantería de Alquiler'),
  ('Desguace')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS customers (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cod_empresa   TEXT,
  razon_social  TEXT NOT NULL,
  cuit          TEXT,
  contacto      TEXT,
  telefono      TEXT,
  telefono_2    TEXT,
  email         TEXT
);

CREATE TABLE IF NOT EXISTS devices (
  id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id      INTEGER  NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  marca_id         INTEGER  NULL REFERENCES marcas(id) ON DELETE SET NULL,
  model_id         INTEGER  NULL REFERENCES models(id) ON DELETE SET NULL,
  numero_serie     TEXT,
  garantia_bool    BOOLEAN,
  propietario      TEXT,
  etiq_garantia_ok BOOLEAN,
  n_de_control     TEXT,
  alquilado        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS ingresos (
  id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  device_id            INTEGER NOT NULL REFERENCES devices(id) ON DELETE RESTRICT,
  estado               ticket_state NOT NULL DEFAULT 'ingresado',
  motivo               motivo_ingreso NOT NULL,
  fecha_ingreso        TIMESTAMPTZ NULL,
  fecha_creacion       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_servicio       TIMESTAMPTZ NULL,
  fecha_entrega        TIMESTAMPTZ NULL,
  ubicacion_id         INTEGER NULL REFERENCES locations(id) ON DELETE SET NULL,
  disposicion          disposicion_type NOT NULL DEFAULT 'normal',
  informe_preliminar   TEXT,
  accesorios           TEXT,
  equipo_variante      TEXT,
  remito_ingreso       TEXT,
  remito_salida        TEXT,
  factura_numero       TEXT,
  recibido_por         INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  comentarios          TEXT,
  garantia_reparacion  BOOLEAN,
  faja_garantia        TEXT,
  presupuesto_estado   quote_estado NOT NULL DEFAULT 'pendiente',
  asignado_a           INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  etiqueta_qr          TEXT NULL,
  alquilado            BOOLEAN,
  alquiler_a           TEXT,
  alquiler_remito      TEXT,
  alquiler_fecha       DATE,
  propietario_nombre   TEXT,
  propietario_contacto TEXT,
  propietario_doc      TEXT,
  descripcion_problema  TEXT,
  trabajos_realizados   TEXT,
  resolucion           TEXT NULL
);

CREATE TABLE IF NOT EXISTS quotes (
  id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id      INTEGER  NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  estado          quote_estado NOT NULL DEFAULT 'pendiente',
  moneda          VARCHAR(10) NOT NULL DEFAULT 'ARS',
  subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,
  iva_21          NUMERIC(12,2) GENERATED ALWAYS AS (round((subtotal * 0.21), 2)) STORED,
  total           NUMERIC(12,2) GENERATED ALWAYS AS (round((subtotal * 1.21), 2)) STORED,
  autorizado_por  TEXT,
  forma_pago      TEXT,
  fecha_emitido   TIMESTAMPTZ NULL,
  fecha_aprobado  TIMESTAMPTZ NULL,
  pdf_url         TEXT,
  CONSTRAINT uq_quotes_ingreso UNIQUE (ingreso_id)
);

CREATE TABLE IF NOT EXISTS quote_items (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quote_id    INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  tipo        quote_item_tipo NOT NULL,
  descripcion TEXT NOT NULL,
  qty         NUMERIC(10,2) NOT NULL DEFAULT 1,
  precio_u    NUMERIC(12,2) NOT NULL,
  repuesto_id INTEGER NULL
);

CREATE TABLE IF NOT EXISTS ingreso_events (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticket_id   INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  ingreso_id  INTEGER GENERATED ALWAYS AS (ticket_id) STORED,
  de_estado   ticket_state NULL,
  a_estado    ticket_state NOT NULL,
  usuario_id  INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
  ts          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  comentario  TEXT
);

CREATE TABLE IF NOT EXISTS ingreso_media (
  id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id     INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  usuario_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  storage_path   TEXT NOT NULL,
  thumbnail_path TEXT NOT NULL,
  original_name  TEXT,
  mime_type      VARCHAR(80) NOT NULL,
  size_bytes     BIGINT NOT NULL,
  width          INTEGER NOT NULL,
  height         INTEGER NOT NULL,
  comentario     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Solicitudes de asignación de técnico (simple, una fila por solicitud)
CREATE TABLE IF NOT EXISTS ingreso_assignment_requests (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id  INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  usuario_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status      TEXT NOT NULL DEFAULT 'pendiente',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  accepted_at TIMESTAMPTZ NULL,
  canceled_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_iars_ingreso_created ON ingreso_assignment_requests(ingreso_id, created_at DESC);

CREATE TABLE IF NOT EXISTS proveedores_externos (
  id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre    TEXT NOT NULL,
  contacto  TEXT,
  telefono  TEXT,
  email     TEXT,
  direccion TEXT,
  notas     TEXT,
  CONSTRAINT uq_prov_ext_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS equipos_derivados (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id    INTEGER  NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  proveedor_id  INTEGER  NOT NULL REFERENCES proveedores_externos(id) ON DELETE RESTRICT,
  remit_deriv   TEXT,
  fecha_deriv   DATE NOT NULL DEFAULT CURRENT_DATE,
  fecha_entrega DATE,
  estado        deriv_estado NOT NULL DEFAULT 'derivado',
  comentarios   TEXT
);

-- Evitar mas de una derivacion "abierta" por ingreso a la vez
CREATE UNIQUE INDEX IF NOT EXISTS uq_equipos_derivados_ingreso_abierto
  ON equipos_derivados(ingreso_id)
  WHERE estado = 'derivado' AND fecha_entrega IS NULL;

CREATE TABLE IF NOT EXISTS handoffs (
  id                     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id             INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  pdf_orden_salida       TEXT,
  firmado_cliente        BOOLEAN,
  firmado_empresa        BOOLEAN,
  fecha                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  n_factura              TEXT,
  factura_url            TEXT,
  orden_taller           TEXT,
  remito_impreso         BOOLEAN,
  fecha_impresion_remito DATE,
  impresion_remito_url   TEXT
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id      INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   TEXT     NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at   TIMESTAMPTZ NOT NULL,
  used_at      TIMESTAMPTZ NULL,
  ip           TEXT,
  user_agent   TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id      INTEGER,
  role         TEXT,
  method       TEXT,
  path         TEXT,
  ip           TEXT,
  user_agent   TEXT,
  status_code  INTEGER,
  body         JSONB
);

-- ===============
-- Audit (change log por columna) para PostgreSQL
-- ===============
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

-- Función genérica de auditoría por fila (INSERT/UPDATE/DELETE)
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
    -- omitir campos de timestamp de sistema comunes
    IF k IN ('updated_at','created_at') THEN CONTINUE; END IF;
    oval := jold->>k;
    nval := jnew->>k;
    IF (oval IS DISTINCT FROM nval) THEN
      INSERT INTO audit.change_log(ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value, ingreso_id)
      VALUES (
        now(),
        NULLIF(_user_id,'')::int,
        NULLIF(_user_role,''),
        tname,
        rec_id,
        k,
        oval,
        nval,
        v_ingreso_id
      );
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$$ LANGUAGE plpgsql;

-- Accesorios (catálogo y vínculo con ingreso)
CREATE TABLE IF NOT EXISTS catalogo_accesorios (
  id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre  TEXT NOT NULL,
  activo  BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_catalogo_accesorios_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS ingreso_accesorios (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id    INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  accesorio_id  INTEGER NOT NULL REFERENCES catalogo_accesorios(id) ON DELETE RESTRICT,
  referencia    TEXT NULL,
  descripcion   TEXT NULL
);

-- Accesorios asociados específicamente a alquileres de equipos
CREATE TABLE IF NOT EXISTS ingreso_alquiler_accesorios (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingreso_id    INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
  accesorio_id  INTEGER NOT NULL REFERENCES catalogo_accesorios(id) ON DELETE RESTRICT,
  referencia    TEXT NULL,
  descripcion   TEXT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Catálogo general de tipos de equipo
CREATE TABLE IF NOT EXISTS catalogo_tipos_equipo (
  id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre     VARCHAR(160) NOT NULL UNIQUE,
  activo     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Catálogo por marca/tipo/serie/variante (jerárquico) y mapeo de models
CREATE TABLE IF NOT EXISTS marca_tipos_equipo (
  id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  marca_id   INTEGER NOT NULL REFERENCES marcas(id) ON DELETE CASCADE,
  nombre     VARCHAR(160) NOT NULL,
  activo     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_marca_tipos_equipo UNIQUE (marca_id, nombre)
);

CREATE TABLE IF NOT EXISTS marca_series (
  id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  marca_id   INTEGER NOT NULL REFERENCES marcas(id) ON DELETE CASCADE,
  tipo_id    INTEGER NOT NULL REFERENCES marca_tipos_equipo(id) ON DELETE CASCADE,
  nombre     VARCHAR(160) NOT NULL,
  alias      VARCHAR(160) NULL,
  activo     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_marca_series UNIQUE (marca_id, tipo_id, nombre)
);

CREATE TABLE IF NOT EXISTS marca_series_variantes (
  id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  marca_id   INTEGER NOT NULL REFERENCES marcas(id) ON DELETE CASCADE,
  tipo_id    INTEGER NOT NULL REFERENCES marca_tipos_equipo(id) ON DELETE CASCADE,
  serie_id   INTEGER NOT NULL REFERENCES marca_series(id) ON DELETE CASCADE,
  nombre     VARCHAR(160) NOT NULL,
  activo     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_marca_series_variantes UNIQUE (marca_id, tipo_id, serie_id, nombre)
);

CREATE TABLE IF NOT EXISTS model_hierarchy (
  id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id    INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
  marca_id    INTEGER NOT NULL REFERENCES marcas(id) ON DELETE CASCADE,
  tipo_id     INTEGER NOT NULL REFERENCES marca_tipos_equipo(id) ON DELETE CASCADE,
  serie_id    INTEGER NOT NULL REFERENCES marca_series(id) ON DELETE CASCADE,
  variante_id INTEGER NULL REFERENCES marca_series_variantes(id) ON DELETE CASCADE,
  full_name   VARCHAR(240) NOT NULL,
  variant_key INTEGER GENERATED ALWAYS AS (COALESCE(variante_id, 0)) STORED,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_model_hierarchy_model UNIQUE (model_id),
  CONSTRAINT uq_model_hierarchy_combo UNIQUE (marca_id, tipo_id, serie_id, variant_key)
);

CREATE OR REPLACE VIEW vw_model_hierarchy_detail AS
SELECT
    mh.model_id,
    mh.marca_id,
    mh.tipo_id,
    mh.serie_id,
    mh.variante_id,
    mh.full_name,
    mt.nombre AS tipo_nombre,
    ms.nombre AS serie_nombre,
    mv.nombre AS variante_nombre
FROM model_hierarchy mh
JOIN marca_tipos_equipo mt ON mt.id = mh.tipo_id
JOIN marca_series ms ON ms.id = mh.serie_id
LEFT JOIN marca_series_variantes mv ON mv.id = mh.variante_id;

-- Feriados (calendario laboral)
CREATE TABLE IF NOT EXISTS feriados (
  fecha DATE PRIMARY KEY,
  nombre TEXT NOT NULL
);

-- =============================
-- Índices
-- =============================
CREATE INDEX IF NOT EXISTS idx_models_marca ON models(marca_id);
CREATE INDEX IF NOT EXISTS idx_models_tecnico ON models(tecnico_id);

CREATE INDEX IF NOT EXISTS idx_devices_customer ON devices(customer_id);
CREATE INDEX IF NOT EXISTS idx_devices_marca ON devices(marca_id);
CREATE INDEX IF NOT EXISTS idx_devices_model ON devices(model_id);
CREATE INDEX IF NOT EXISTS idx_devices_nro_serie ON devices(numero_serie);

CREATE INDEX IF NOT EXISTS idx_ingresos_device ON ingresos(device_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_ubicacion ON ingresos(ubicacion_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_asignado ON ingresos(asignado_a);
CREATE INDEX IF NOT EXISTS ix_ingresos_asignado_estado ON ingresos(asignado_a, estado);

CREATE INDEX IF NOT EXISTS idx_quotes_ingreso ON quotes(ingreso_id);
CREATE INDEX IF NOT EXISTS ix_quotes_emitido ON quotes(fecha_emitido);
CREATE INDEX IF NOT EXISTS ix_quotes_aprobado ON quotes(fecha_aprobado);

CREATE INDEX IF NOT EXISTS idx_items_quote ON quote_items(quote_id);
CREATE INDEX IF NOT EXISTS ix_events_ingreso_estado_ts ON ingreso_events(ingreso_id, a_estado, ts);

CREATE INDEX IF NOT EXISTS idx_ingreso_acc_ingreso ON ingreso_accesorios(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_ingreso_acc_accesorio ON ingreso_accesorios(accesorio_id);

CREATE INDEX IF NOT EXISTS idx_ingreso_alq_acc_ingreso ON ingreso_alquiler_accesorios(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_ingreso_alq_acc_accesorio ON ingreso_alquiler_accesorios(accesorio_id);

CREATE INDEX IF NOT EXISTS idx_mte_marca ON marca_tipos_equipo(marca_id);
CREATE INDEX IF NOT EXISTS idx_ms_tipo   ON marca_series(tipo_id);
CREATE INDEX IF NOT EXISTS idx_msv_tipo  ON marca_series_variantes(tipo_id);
CREATE INDEX IF NOT EXISTS idx_msv_serie ON marca_series_variantes(serie_id);
CREATE INDEX IF NOT EXISTS idx_mh_tipo   ON model_hierarchy(tipo_id);
CREATE INDEX IF NOT EXISTS idx_mh_serie  ON model_hierarchy(serie_id);
CREATE INDEX IF NOT EXISTS idx_mh_var    ON model_hierarchy(variante_id);

-- Unicidad case-insensitive (nombres) mediante índices únicos funcionales
CREATE UNIQUE INDEX IF NOT EXISTS uq_marcas_nombre_ci ON marcas ((LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_models_marca_nombre_ci ON models (marca_id, (LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_catalogo_accesorios_nombre_ci ON catalogo_accesorios ((LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_catalogo_tipos_equipo_nombre_ci ON catalogo_tipos_equipo ((LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_mte_ci ON marca_tipos_equipo (marca_id, (LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_ms_ci ON marca_series (marca_id, tipo_id, (LOWER(nombre)));
CREATE UNIQUE INDEX IF NOT EXISTS uq_msv_ci ON marca_series_variantes (marca_id, tipo_id, serie_id, (LOWER(nombre)));

-- =============================
-- Triggers
-- =============================
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_ingreso_media_set_updated_at') THEN
    CREATE TRIGGER trg_ingreso_media_set_updated_at
    BEFORE UPDATE ON ingreso_media
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_cte_updated_at') THEN
    CREATE TRIGGER trg_cte_updated_at BEFORE UPDATE ON catalogo_tipos_equipo
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_mte_updated_at') THEN
    CREATE TRIGGER trg_mte_updated_at BEFORE UPDATE ON marca_tipos_equipo
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_ms_updated_at') THEN
    CREATE TRIGGER trg_ms_updated_at BEFORE UPDATE ON marca_series
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_msv_updated_at') THEN
    CREATE TRIGGER trg_msv_updated_at BEFORE UPDATE ON marca_series_variantes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_mh_updated_at') THEN
    CREATE TRIGGER trg_mh_updated_at BEFORE UPDATE ON model_hierarchy
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  -- audit_log append-only
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_log_no_update') THEN
    CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_update();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_log_no_delete') THEN
    CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_update();
  END IF;
  -- sync de quotes -> ingresos
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_quote_sync_ins') THEN
    CREATE TRIGGER trg_quote_sync_ins AFTER INSERT ON quotes
    FOR EACH ROW EXECUTE FUNCTION sync_quote_with_ingreso();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_quote_sync_upd') THEN
    CREATE TRIGGER trg_quote_sync_upd AFTER UPDATE OF estado, subtotal, fecha_emitido, fecha_aprobado ON quotes
    FOR EACH ROW EXECUTE FUNCTION sync_quote_with_ingreso();
  END IF;
END $$;

-- Activar triggers de auditoría por fila (si no existen)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingresos') THEN
    CREATE TRIGGER trg_audit_ingresos
    AFTER INSERT OR UPDATE OR DELETE ON ingresos
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_devices') THEN
    CREATE TRIGGER trg_audit_devices
    AFTER INSERT OR UPDATE OR DELETE ON devices
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingreso_accesorios') THEN
    CREATE TRIGGER trg_audit_ingreso_accesorios
    AFTER INSERT OR UPDATE OR DELETE ON ingreso_accesorios
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_ingreso_alquiler_accesorios') THEN
    CREATE TRIGGER trg_audit_ingreso_alquiler_accesorios
    AFTER INSERT OR UPDATE OR DELETE ON ingreso_alquiler_accesorios
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_quotes') THEN
    CREATE TRIGGER trg_audit_quotes
    AFTER INSERT OR UPDATE OR DELETE ON quotes
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_quote_items') THEN
    CREATE TRIGGER trg_audit_quote_items
    AFTER INSERT OR UPDATE OR DELETE ON quote_items
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
END $$;
