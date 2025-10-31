-- Paso 1: Migración focalizada en Devices
-- Motor: PostgreSQL
-- Objetivo:
--   1) Backfill devices.numero_interno desde devices.n_de_control cuando esté vacío/nulo
--   2) Recalcular devices.n_de_control como snapshot de ingresos.faja_garantia del último ingreso por equipo

BEGIN;

-- 1) Asegurar columna (idempotente)
ALTER TABLE devices ADD COLUMN IF NOT EXISTS numero_interno TEXT;

-- 2) Backfill numero_interno desde n_de_control solo donde falte
WITH cand AS (
  SELECT d.id,
         UPPER(REGEXP_REPLACE(NULLIF(d.n_de_control,''),
           '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) AS norm
    FROM devices d
   WHERE (d.numero_interno IS NULL OR d.numero_interno = '')
     AND NULLIF(d.n_de_control,'') IS NOT NULL
)
UPDATE devices d
   SET numero_interno = c.norm
  FROM cand c
 WHERE d.id = c.id
   AND c.norm IS NOT NULL
   AND NOT EXISTS (
     SELECT 1 FROM devices x
      WHERE x.id <> d.id
        AND UPPER(REGEXP_REPLACE(x.numero_interno,
            '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) = c.norm
   );

-- 3) Snapshot n_de_control desde el último ingreso (por fecha_ingreso/fecha_creacion más reciente y id)
WITH last_ingreso AS (
  SELECT DISTINCT ON (t.device_id)
         t.device_id,
         NULLIF(t.faja_garantia,'') AS faja
    FROM ingresos t
   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
)
UPDATE devices d
   SET n_de_control = COALESCE(li.faja, d.n_de_control)
  FROM last_ingreso li
 WHERE d.id = li.device_id;

COMMIT;
