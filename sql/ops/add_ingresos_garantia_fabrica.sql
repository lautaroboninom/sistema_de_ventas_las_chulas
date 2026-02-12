-- Agrega columna de garantía de fábrica por ingreso y realiza backfill desde devices
-- Idempotente (PostgreSQL 12+)

BEGIN;

ALTER TABLE ingresos
  ADD COLUMN IF NOT EXISTS garantia_fabrica BOOLEAN;

-- Backfill inicial: copiar el valor actual del dispositivo asociado
UPDATE ingresos i
   SET garantia_fabrica = COALESCE(d.garantia_bool, false)
  FROM devices d
 WHERE d.id = i.device_id
   AND i.garantia_fabrica IS NULL;

COMMIT;

