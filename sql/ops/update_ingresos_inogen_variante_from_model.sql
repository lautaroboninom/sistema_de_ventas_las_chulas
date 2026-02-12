-- Actualiza ingresos: pone el modelo como variante
-- Caso: equipos marca INOGEN con modelo en {G2, G3, G4, G5, ONE G5}
-- Efecto: ingresos.equipo_variante = m.nombre (o 'G5' si el modelo es 'ONE G5', ver alternativa)

-- 1) Vista previa (recomendado antes de ejecutar el UPDATE)
--    Lista los ingresos alcanzados y su variante actual
-- SELECT i.id AS ingreso_id,
--        b.nombre AS marca,
--        m.nombre AS modelo,
--        NULLIF(i.equipo_variante, '') AS variante_actual
--   FROM ingresos i
--   JOIN devices d ON d.id = i.device_id
--   LEFT JOIN marcas b ON b.id = d.marca_id
--   LEFT JOIN models m ON m.id = d.model_id
--  WHERE b.nombre ILIKE 'INOGEN'
--    AND (
--         m.nombre IN ('G2','G3','G4','G5')
--         OR m.nombre ILIKE 'ONE G5'
--    )
--  ORDER BY i.id;

-- 2) Update: copia el modelo a la variante del ingreso
--    y normaliza 'ONE G5' -> 'G5'
BEGIN;

UPDATE ingresos i
   SET equipo_variante = CASE WHEN m.nombre ILIKE 'ONE G5' THEN 'G5' ELSE m.nombre END
  FROM devices d
  JOIN models m ON m.id = d.model_id
  JOIN marcas b ON b.id = d.marca_id
 WHERE i.device_id = d.id
   AND b.nombre ILIKE 'INOGEN'
   AND (
        m.nombre IN ('G2','G3','G4','G5')
        OR m.nombre ILIKE 'ONE G5'
   );

COMMIT;

-- 3) Verificación rápida
-- SELECT COUNT(*) AS cant
--   FROM ingresos i
--   JOIN devices d ON d.id = i.device_id
--   JOIN marcas b ON b.id = d.marca_id
--   JOIN models m ON m.id = d.model_id
--  WHERE b.nombre ILIKE 'INOGEN'
--    AND (
--         m.nombre IN ('G2','G3','G4','G5')
--         OR m.nombre ILIKE 'ONE G5'
--    )
--    AND NULLIF(i.equipo_variante, '') = CASE WHEN m.nombre ILIKE 'ONE G5' THEN 'G5' ELSE m.nombre END;
