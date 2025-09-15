SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_ing_motivo;
CREATE TEMPORARY TABLE staging_ing_motivo ( ingreso_id INT, motivo_id INT );
LOAD DATA LOCAL INFILE '/tmp/etl/ingresos_motivo_access.csv'
INTO TABLE staging_ing_motivo
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (ingreso_id, motivo_id);

UPDATE ingresos t
JOIN staging_ing_motivo s ON s.ingreso_id = t.id
SET t.motivo = (
  CASE s.motivo_id
    WHEN 1 THEN 'reparación'
    WHEN 2 THEN 'service preventivo'
    WHEN 3 THEN 'baja alquiler'
    WHEN 4 THEN 'reparación alquiler'
    WHEN 5 THEN 'otros'
    WHEN 6 THEN 'devolución demo'
    ELSE 'otros'
  END
);
SET FOREIGN_KEY_CHECKS=1;
