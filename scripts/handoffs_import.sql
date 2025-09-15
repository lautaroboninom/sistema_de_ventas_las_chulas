SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_handoffs;
CREATE TEMPORARY TABLE staging_handoffs (
  id INT,
  ingreso_id INT,
  pdf_orden_salida TEXT,
  firmado_cliente TEXT,
  firmado_empresa TEXT,
  fecha TEXT,
  n_factura TEXT,
  factura_url TEXT,
  orden_taller TEXT,
  remito_impreso TEXT,
  fecha_impresion_remito TEXT,
  impresion_remito_url TEXT
);
LOAD DATA INFILE '/var/lib/mysql-files/handoffs.csv'
INTO TABLE staging_handoffs
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, ingreso_id, pdf_orden_salida, firmado_cliente, firmado_empresa, fecha, n_factura, factura_url, orden_taller, remito_impreso, fecha_impresion_remito, impresion_remito_url);

REPLACE INTO handoffs (id, ingreso_id, pdf_orden_salida, firmado_cliente, firmado_empresa, fecha, n_factura, factura_url, orden_taller, remito_impreso, fecha_impresion_remito, impresion_remito_url)
SELECT
  NULLIF(id,''),
  NULLIF(ingreso_id,''),
  NULLIF(pdf_orden_salida,''),
  CASE
    WHEN LOWER(TRIM(firmado_cliente)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(firmado_cliente)) IN ('f','false','0','n','no') THEN 0
    WHEN firmado_cliente = '' THEN NULL
    ELSE NULL
  END,
  CASE
    WHEN LOWER(TRIM(firmado_empresa)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(firmado_empresa)) IN ('f','false','0','n','no') THEN 0
    WHEN firmado_empresa = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(fecha,''),
  NULLIF(n_factura,''),
  NULLIF(factura_url,''),
  NULLIF(orden_taller,''),
  CASE
    WHEN LOWER(TRIM(remito_impreso)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(remito_impreso)) IN ('f','false','0','n','no') THEN 0
    WHEN remito_impreso = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(fecha_impresion_remito,''),
  NULLIF(impresion_remito_url,'')
FROM staging_handoffs;
DROP TEMPORARY TABLE staging_handoffs;
SET FOREIGN_KEY_CHECKS=1;

