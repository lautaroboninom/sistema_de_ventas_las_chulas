-- Triage de ingresos: staging table que refleja columnas del CSV
DROP TABLE IF EXISTS stg_ingresos;
CREATE TABLE stg_ingresos (
  row_num INT PRIMARY KEY AUTO_INCREMENT,
  id TEXT,
  device_id TEXT,
  estado TEXT,
  motivo TEXT,
  fecha_ingreso TEXT,
  sala_origen TEXT,
  ubicacion_id TEXT,
  disposicion TEXT,
  informe_preliminar TEXT,
  accesorios TEXT,
  remito_ingreso TEXT,
  recibido_por TEXT,
  comentarios TEXT,
  presupuesto_estado TEXT,
  asignado_a TEXT,
  etiqueta_qr TEXT,
  propietario_nombre TEXT,
  propietario_contacto TEXT,
  propietario_doc TEXT,
  descripcion_problema TEXT,
  trabajos_realizados TEXT,
  fecha_servicio TEXT,
  resolucion TEXT,
  garantia_reparacion TEXT,
  faja_garantia TEXT,
  remito_salida TEXT,
  factura_numero TEXT,
  fecha_entrega TEXT,
  alquilado TEXT,
  alquiler_a TEXT,
  alquiler_remito TEXT,
  alquiler_fecha TEXT
) ENGINE=InnoDB;

LOAD DATA INFILE '/var/lib/mysql-files/ingresos.csv'
INTO TABLE stg_ingresos
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(
 id, device_id, estado, motivo, fecha_ingreso, sala_origen, ubicacion_id, disposicion, informe_preliminar, accesorios,
 remito_ingreso, recibido_por, comentarios, presupuesto_estado, asignado_a, etiqueta_qr, propietario_nombre,
 propietario_contacto, propietario_doc, descripcion_problema, trabajos_realizados, fecha_servicio, resolucion,
 garantia_reparacion, faja_garantia, remito_salida, factura_numero, fecha_entrega, alquilado, alquiler_a, alquiler_remito, alquiler_fecha
);

SELECT COUNT(*) AS stg_rows FROM stg_ingresos;

-- Comparación con tabla destino
SELECT (SELECT COUNT(*) FROM stg_ingresos) AS csv_rows,
       (SELECT COUNT(*) FROM ingresos)     AS mysql_rows;

SELECT CAST(s.id AS UNSIGNED) AS missing_id
  FROM stg_ingresos s
  LEFT JOIN ingresos t ON t.id = CAST(s.id AS UNSIGNED)
 WHERE t.id IS NULL
 ORDER BY CAST(s.id AS UNSIGNED)
 LIMIT 50;

SELECT DISTINCT estado FROM stg_ingresos ORDER BY 1;
SELECT DISTINCT presupuesto_estado FROM stg_ingresos ORDER BY 1;
SELECT DISTINCT motivo FROM stg_ingresos ORDER BY 1;

SELECT etiqueta_qr, COUNT(*) cnt FROM stg_ingresos
 WHERE COALESCE(etiqueta_qr,'') <> ''
 GROUP BY etiqueta_qr HAVING cnt>1 ORDER BY cnt DESC LIMIT 20;
