-- Sincroniza ingresos.equipo_variante a partir de:
--  A) models.variante (si está presente)
--  B) Heurística por nombre de modelo (por ahora: INOGEN 'G#' / 'ONE G#' -> 'G#')

BEGIN;

-- A) Copiar desde models.variante cuando equipo_variante está vacío
UPDATE ingresos i
   SET equipo_variante = NULLIF(TRIM(m.variante), '')
  FROM devices d
  JOIN models m ON m.id = d.model_id
 WHERE i.device_id = d.id
   AND (i.equipo_variante IS NULL OR i.equipo_variante = '')
   AND NULLIF(TRIM(m.variante), '') IS NOT NULL;

-- B) Heurística INOGEN: extraer 'G#' del nombre del modelo (incluye 'ONE G#')
WITH matches AS (
  SELECT i.id AS ingreso_id,
         UPPER('G' || (regexp_matches(UPPER(m.nombre), '(?:ONE\s*)?G\s*(\d+)'))[1]) AS var
    FROM ingresos i
    JOIN devices d ON d.id = i.device_id
    JOIN models m ON m.id = d.model_id
    JOIN marcas b ON b.id = d.marca_id
   WHERE (i.equipo_variante IS NULL OR i.equipo_variante = '')
     AND b.nombre ILIKE 'INOGEN'
     AND UPPER(m.nombre) ~ '(?:ONE\s*)?G\s*\d+'
)
UPDATE ingresos i
   SET equipo_variante = matches.var
  FROM matches
 WHERE i.id = matches.ingreso_id;

COMMIT;

-- Verificación rápida (opcional)
-- SELECT i.id, b.nombre AS marca, m.nombre AS modelo, i.equipo_variante
--   FROM ingresos i
--   JOIN devices d ON d.id = i.device_id
--   JOIN marcas b ON b.id = d.marca_id
--   JOIN models m ON m.id = d.model_id
--  WHERE (m.variante IS NOT NULL AND m.variante <> '') OR (b.nombre ILIKE 'INOGEN' AND UPPER(m.nombre) ~ '(?:ONE\s*)?G\s*\d+')
--  ORDER BY i.id;

