DROP TABLE IF EXISTS staging_ingresos_alquiler;
CREATE TABLE staging_ingresos_alquiler (
  ingreso_id INT,
  alquilado_flag TEXT,
  recibe_alquiler TEXT,
  cargo_alquiler TEXT
) ENGINE=InnoDB;
LOAD DATA LOCAL INFILE '/tmp/etl_out/ingresos_alquiler_access.csv'
INTO TABLE staging_ingresos_alquiler
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(ingreso_id, alquilado_flag, recibe_alquiler, cargo_alquiler);

-- Normalizar bandera y datos de alquiler en ingresos y devices
UPDATE ingresos t
JOIN staging_ingresos_alquiler s ON s.ingreso_id = t.id
   SET t.alquiler_a      = NULLIF(s.recibe_alquiler,''),
       t.alquilado       = CASE WHEN LOWER(TRIM(COALESCE(s.alquilado_flag,''))) IN ('1','-1','t','true','y','yes','si','s','s?') OR NULLIF(s.recibe_alquiler,'')<>'' OR NULLIF(s.cargo_alquiler,'')<>'' THEN 1 ELSE t.alquilado END,
       t.estado          = CASE WHEN (LOWER(TRIM(COALESCE(s.alquilado_flag,''))) IN ('1','-1','t','true','y','yes','si','s','s?') OR NULLIF(s.recibe_alquiler,'')<>'' OR NULLIF(s.cargo_alquiler,'')<>'' ) THEN 'alquilado' ELSE t.estado END;

UPDATE devices d
JOIN ingresos t ON t.device_id = d.id
JOIN staging_ingresos_alquiler s ON s.ingreso_id = t.id
   SET d.alquilado = CASE WHEN LOWER(TRIM(COALESCE(s.alquilado_flag,''))) IN ('1','-1','t','true','y','yes','si','s','s?') OR NULLIF(s.recibe_alquiler,'')<>'' OR NULLIF(s.cargo_alquiler,'')<>'' THEN 1 ELSE d.alquilado END;

-- Resumen
SELECT COUNT(*) AS n_alquiler_rows FROM staging_ingresos_alquiler;
SELECT SUM(t.estado='alquilado') AS total_estado_alquilado FROM ingresos t;

DROP TABLE staging_ingresos_alquiler;
