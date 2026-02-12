-- Rollback: elimina variantes 'G#' asignadas por heurística para marcas NO INOGEN
-- Objetivo: revertir BMC/RESMART/BMXC (mantener INOGEN tal como está)

BEGIN;

WITH matches AS (
  SELECT i.id AS ingreso_id,
         UPPER('G' || (regexp_matches(UPPER(m.nombre), '(?:ONE\s*)?G\s*(\d+)'))[1]) AS var,
         b.nombre AS marca
    FROM ingresos i
    JOIN devices d ON d.id = i.device_id
    JOIN models m ON m.id = d.model_id
    JOIN marcas b ON b.id = d.marca_id
   WHERE UPPER(m.nombre) ~ '(?:ONE\s*)?G\s*\d+'
     AND b.nombre ILIKE ANY (ARRAY['BMC','RESMART','BMXC'])
)
UPDATE ingresos i
   SET equipo_variante = NULL
  FROM matches
 WHERE i.id = matches.ingreso_id
   AND COALESCE(i.equipo_variante,'') <> ''
   AND TRIM(i.equipo_variante) = matches.var;

COMMIT;

