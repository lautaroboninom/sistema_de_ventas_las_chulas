SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_estado_entrega;
CREATE TEMPORARY TABLE staging_estado_entrega (
  ingreso_id INT,
  estado_nombre TEXT,
  entregado TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/ingresos_estado_entrega_access.csv'
INTO TABLE staging_estado_entrega
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (ingreso_id, estado_nombre, entregado);

SELECT 'loaded_rows' AS tag, COUNT(*) AS n FROM staging_estado_entrega;

SELECT 'estado_top' AS tag, LOWER(TRIM(estado_nombre)) AS e, COUNT(*) c
FROM staging_estado_entrega GROUP BY e ORDER BY c DESC LIMIT 12;

-- delivered
SELECT 'delivered_rows' AS tag, COUNT(*) AS n FROM staging_estado_entrega
WHERE LOWER(TRIM(entregado)) IN ('1','t','true','y','yes','si','sí');

-- Update resolucion
UPDATE ingresos t
JOIN staging_estado_entrega s ON s.ingreso_id = t.id
SET t.resolucion = (
  CASE
    WHEN LOWER(TRIM(s.estado_nombre)) LIKE 'reparado%' THEN 'reparado'
    WHEN LOWER(TRIM(s.estado_nombre)) LIKE 'sin reparar%' THEN 'no_reparado'
    WHEN LOWER(TRIM(s.estado_nombre)) LIKE 'controlado%' THEN 'no_se_encontro_falla'
    WHEN LOWER(TRIM(s.estado_nombre)) LIKE 'presup.%rechazado%' OR LOWER(TRIM(s.estado_nombre)) LIKE 'presup.rechazado%' THEN 'presupuesto_rechazado'
    ELSE t.resolucion
  END
);

-- delivered update
UPDATE ingresos t
JOIN staging_estado_entrega s ON s.ingreso_id = t.id
SET t.estado = 'entregado'
WHERE LOWER(TRIM(s.entregado)) IN ('1','t','true','y','yes','si','sí');

SELECT 'resolucion_counts' AS tag, resolucion, COUNT(*) c FROM ingresos GROUP BY resolucion;
SELECT 'entregados_counts' AS tag, estado, COUNT(*) c FROM ingresos GROUP BY estado;

SET FOREIGN_KEY_CHECKS=1;
