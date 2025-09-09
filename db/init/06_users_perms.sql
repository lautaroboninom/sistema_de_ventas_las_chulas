-- 1) Ampliar el CHECK de roles para incluir 'jefe_veedor' si faltara
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.users'::regclass
      AND conname  = 'users_rol_check'
      AND pg_get_constraintdef(oid) NOT LIKE '%jefe_veedor%'
  ) THEN
    ALTER TABLE users DROP CONSTRAINT users_rol_check;
    ALTER TABLE users
      ADD CONSTRAINT users_rol_check
      CHECK (rol IN ('jefe','jefe_veedor','tecnico','admin','recepcion','auditor'));
  END IF;
END$$;

-- 2) Asegurar columnas de técnico por marca/modelo (por si venías de una versión sin esto)
ALTER TABLE marcas  ADD COLUMN IF NOT EXISTS tecnico_id int REFERENCES users(id);
ALTER TABLE models  ADD COLUMN IF NOT EXISTS tecnico_id int REFERENCES users(id);
CREATE INDEX IF NOT EXISTS idx_marcas_tecnico ON marcas(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_models_tecnico ON models(tecnico_id);

-- 3) Crear catálogo y log de derivaciones si no existieran (fresh/legacy-safe)
CREATE TABLE IF NOT EXISTS proveedores_externos (
  id       SERIAL PRIMARY KEY,
  nombre   TEXT NOT NULL UNIQUE,
  contacto TEXT
);

CREATE TYPE external_state AS ENUM ('derivado','en_servicio','devuelto','entregado_cliente')
  -- sólo si no existía:
  -- en PG 11+ esto falla si ya existe; lo envolvemos:
  -- (ya lo trae tu 01_schema.sql, esto es de seguridad por legacy)
;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='equipos_derivados'
  ) THEN
    CREATE TABLE equipos_derivados (
      id             SERIAL PRIMARY KEY,
      ingreso_id     INT NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
      proveedor_id   INT NOT NULL REFERENCES proveedores_externos(id),
      remit_deriv    TEXT,
      fecha_deriv    DATE,
      fecha_entrega  DATE,
      estado         external_state NOT NULL DEFAULT 'derivado',
      comentarios    TEXT
    );
    CREATE INDEX idx_equipos_derivados_ingreso ON equipos_derivados(ingreso_id);
    CREATE INDEX idx_equipos_derivados_prov    ON equipos_derivados(proveedor_id);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_equipos_derivados_ingreso_fecha
      ON equipos_derivados(ingreso_id, COALESCE(fecha_deriv, DATE '1970-01-01'));
  END IF;
END$$;

-- 4) Backfill desde la tabla legacy external_services (si existe)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='external_services'
  ) THEN

    -- 4.1) Poblar catálogo
    INSERT INTO proveedores_externos(nombre)
    SELECT DISTINCT proveedor
    FROM external_services
    WHERE COALESCE(proveedor,'') <> ''
    ON CONFLICT (nombre) DO NOTHING;

    -- 4.2) Mapear estados (entregado_cliente -> devuelto)
    WITH m AS (
      SELECT
        es.*,
        pe.id AS proveedor_id_new,
        CASE
          WHEN es.estado::text = 'entregado_cliente' THEN 'devuelto'
          ELSE es.estado::text
        END AS estado_new
      FROM external_services es
      LEFT JOIN proveedores_externos pe ON pe.nombre = es.proveedor
    )
    INSERT INTO equipos_derivados(ingreso_id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega, estado, comentarios)
    SELECT
      m.ticket_id     AS ingreso_id,
      m.proveedor_id_new,
      m.remit_derivac,
      m.fecha_deriv,
      m.fecha_entrega_deriv,
      m.estado_new::external_state,
      m.comentarios
    FROM m
    WHERE m.proveedor_id_new IS NOT NULL
    ON CONFLICT (ingreso_id, COALESCE(fecha_deriv, DATE '1970-01-01')) DO NOTHING;

    -- 4.3) Reflejar estado del ingreso si la última derivación está abierta
    WITH ult AS (
      SELECT e.ingreso_id,
             (ARRAY_AGG(e.estado ORDER BY e.fecha_deriv DESC NULLS LAST, e.id DESC))[1] AS ult_estado,
             (ARRAY_AGG(e.fecha_entrega ORDER BY e.fecha_deriv DESC NULLS LAST, e.id DESC))[1] AS ult_entrega
      FROM equipos_derivados e
      GROUP BY e.ingreso_id
    )
    UPDATE ingresos t
    SET estado = 'derivado'
    FROM ult
    WHERE ult.ingreso_id = t.id
      AND (ult_estaDO IN ('derivado','en_servicio') OR (ult_estado = 'devuelto' AND ult_entrega IS NULL))
      AND t.estado <> 'derivado';
  END IF;
END$$;

-- 5) Invariante de “perm_ingresar”: jefe sí, técnico no
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_ingresar boolean NOT NULL DEFAULT false;
UPDATE users SET perm_ingresar = true WHERE rol IN ('jefe','jefe_veedor') AND perm_ingresar IS DISTINCT FROM true;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.users'::regclass
      AND conname  = 'users_perm_ingresar_tecnico_chk'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT users_perm_ingresar_tecnico_chk
      CHECK (NOT (rol = 'tecnico' AND perm_ingresar = true));
  END IF;
END$$;
