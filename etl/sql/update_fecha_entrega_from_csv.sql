-- Carga fechas de entrega históricas desde CSV exportado de Access
-- Requiere: archivo accesible en /tmp/ingresos_entrega_access.csv dentro del contenedor MySQL
-- Formato CSV (UTF-8, encabezado): ingreso_id,fecha_entrega (yyyy-MM-dd HH:mm:ss)


DROP TEMPORARY TABLE IF EXISTS tmp_entrega_csv;
CREATE TEMPORARY TABLE tmp_entrega_csv (
  ingreso_id INT PRIMARY KEY,
  fecha_entrega DATETIME NULL
) ENGINE=Memory;

LOAD DATA LOCAL INFILE '/tmp/ingresos_entrega_access.csv'
INTO TABLE tmp_entrega_csv
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(ingreso_id, @fecha_str)
SET fecha_entrega = NULLIF(@fecha_str, '');

-- Actualiza solo entregados; no toca los 40 no-entregados
UPDATE ingresos t
JOIN tmp_entrega_csv e ON e.ingreso_id = t.id AND e.fecha_entrega IS NOT NULL
SET t.fecha_entrega = e.fecha_entrega
WHERE t.estado = 'entregado';

-- Limpieza
DROP TEMPORARY TABLE IF EXISTS tmp_entrega_csv;
