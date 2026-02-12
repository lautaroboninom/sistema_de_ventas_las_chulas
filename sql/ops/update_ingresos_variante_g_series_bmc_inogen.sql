-- Extrae variante 'G#' desde el nombre de modelo para marcas BMC/RESMART/BMXC/INOGEN
-- Solo aplica donde ingresos.equipo_variante está vacío

BEGIN;

WITH matches AS (
  SELECT i.id AS ingreso_id,
         UPPER('G' || (regexp_matches(UPPER(m.nombre), '(?:ONE\s*)?G\s*(\d+)'))[1]) AS var
    FROM ingresos i
    JOIN devices d ON d.id = i.device_id
    JOIN models m ON m.id = d.model_id
    JOIN marcas b ON b.id = d.marca_id
   WHERE (i.equipo_variante IS NULL OR i.equipo_variante = '')
     AND (b.nombre ILIKE 'BMC' OR b.nombre ILIKE 'RESMART' OR b.nombre ILIKE 'BMXC' OR b.nombre ILIKE 'INOGEN')
     AND UPPER(m.nombre) ~ '(?:ONE\s*)?G\s*\d+'
)
UPDATE ingresos i
   SET equipo_variante = matches.var
  FROM matches
 WHERE i.id = matches.ingreso_id;

COMMIT;

