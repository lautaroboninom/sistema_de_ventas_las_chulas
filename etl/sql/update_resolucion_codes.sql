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

UPDATE ingresos t
JOIN staging_estado_entrega s ON s.ingreso_id = t.id
SET t.resolucion = (
  CASE TRIM(s.estado_nombre)
    WHEN '3' THEN 'reparado'
    WHEN '4' THEN 'no_reparado'
    WHEN '9' THEN 'no_se_encontro_falla'
    WHEN '7' THEN 'presupuesto_rechazado'
    ELSE t.resolucion
  END
);

SET FOREIGN_KEY_CHECKS=1;
