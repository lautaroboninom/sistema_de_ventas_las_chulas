-- etl/sql/validation_costos_vs_quotes.sql
-- Requiere: ejecutar antes etl/export_access.ps1 para generar etl/out/reg_serv_costos_access.csv
-- Cómo ejecutar (desde la raíz del repo):
--   mysql --local-infile=1 -h 127.0.0.1 -P 3306 -u sepid -p servicio_tecnico < etl/sql/validation_costos_vs_quotes.sql

SET NAMES utf8mb4;

-- Cargar costos desde Access (RegistrosdeServicio.CostoTotal)
DROP TEMPORARY TABLE IF EXISTS vali_regcost;
CREATE TEMPORARY TABLE vali_regcost (
  ingreso_id INT,
  costo_mano_obra TEXT,
  costo_repuestos TEXT,
  costo_total TEXT,
  autorizado_por TEXT
);
LOAD DATA LOCAL INFILE 'etl/out/reg_serv_costos_access.csv'
INTO TABLE vali_regcost
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(ingreso_id, costo_mano_obra, costo_repuestos, costo_total, autorizado_por);

-- Resumen por mes/cliente: Access(CostoTotal) vs MySQL(quotes.subtotal/total)
SELECT
  c.razon_social                               AS cliente,
  DATE_FORMAT(COALESCE(q.fecha_aprobado, q.fecha_emitido, i.fecha_ingreso), '%Y-%m') AS mes,
  ROUND(SUM(COALESCE(CAST(NULLIF(v.costo_total,'') AS DECIMAL(12,2)), 0)), 2)         AS access_costo_total_sum,
  ROUND(SUM(q.subtotal), 2)                                                          AS mysql_subtotal_sum,
  ROUND(SUM(q.total), 2)                                                             AS mysql_total_sum,
  ROUND(SUM(q.subtotal) - SUM(COALESCE(CAST(NULLIF(v.costo_total,'') AS DECIMAL(12,2)), 0)), 2) AS diff_subtotal,
  COUNT(*)                                                                           AS ingresos
FROM ingresos i
JOIN devices  d ON d.id = i.device_id
JOIN customers c ON c.id = d.customer_id
JOIN quotes   q ON q.ingreso_id = i.id
LEFT JOIN vali_regcost v ON v.ingreso_id = i.id
GROUP BY cliente, mes
ORDER BY mes DESC, cliente ASC;

-- Detalle de diferencias por ingreso (> $0.01)
SELECT
  i.id AS ingreso_id,
  c.razon_social AS cliente,
  DATE_FORMAT(COALESCE(q.fecha_aprobado, q.fecha_emitido, i.fecha_ingreso), '%Y-%m-%d') AS fecha_ref,
  CAST(NULLIF(v.costo_total,'') AS DECIMAL(12,2)) AS access_costo_total,
  q.subtotal AS mysql_subtotal,
  (q.subtotal - CAST(NULLIF(v.costo_total,'') AS DECIMAL(12,2))) AS diff_subtotal,
  q.total AS mysql_total
FROM ingresos i
JOIN devices  d ON d.id = i.device_id
JOIN customers c ON c.id = d.customer_id
JOIN quotes   q ON q.ingreso_id = i.id
LEFT JOIN vali_regcost v ON v.ingreso_id = i.id
WHERE ABS(COALESCE(q.subtotal - CAST(NULLIF(v.costo_total,'') AS DECIMAL(12,2)), q.subtotal)) > 0.01
ORDER BY fecha_ref DESC, ingreso_id DESC
LIMIT 200;

