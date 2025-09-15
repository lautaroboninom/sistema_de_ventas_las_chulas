SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

-- Load models from Access
DROP TEMPORARY TABLE IF EXISTS staging_models2;
CREATE TEMPORARY TABLE staging_models2 ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/models_access.csv'
INTO TABLE staging_models2
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (marca_nombre, nombre);

-- Normalize helpers
DROP TEMPORARY TABLE IF EXISTS brand_map;
CREATE TEMPORARY TABLE brand_map AS
SELECT b.id,
       TRIM(b.nombre) AS nombre,
       LOWER(REPLACE(REPLACE(TRIM(b.nombre), CHAR(13), ''), CHAR(10), '')) AS norm
FROM marcas b;

-- Insert missing models (normalize marca_nombre)
INSERT IGNORE INTO models(marca_id, nombre)
SELECT bm.id, TRIM(REPLACE(REPLACE(sm.nombre, CHAR(13), ''), CHAR(10), ''))
FROM staging_models2 sm
JOIN brand_map bm ON bm.norm = LOWER(REPLACE(REPLACE(TRIM(sm.marca_nombre), CHAR(13), ''), CHAR(10), ''))
WHERE NULLIF(TRIM(sm.nombre),'') IS NOT NULL;

-- Load devices access
DROP TEMPORARY TABLE IF EXISTS staging_devices2;
CREATE TEMPORARY TABLE staging_devices2 (
  id INT,
  customer_cod_empresa TEXT,
  marca_nombre TEXT,
  modelo_nombre TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/devices_access.csv'
INTO TABLE staging_devices2
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(id, customer_cod_empresa, marca_nombre, modelo_nombre, @a,@b,@c,@d,@e);

-- Update devices.marca_id
UPDATE devices d
JOIN staging_devices2 sd ON sd.id = d.id
JOIN brand_map bm ON bm.norm = LOWER(REPLACE(REPLACE(TRIM(sd.marca_nombre), CHAR(13), ''), CHAR(10), ''))
SET d.marca_id = bm.id
WHERE d.marca_id IS NULL;

-- Ensure models exist for device pairs
INSERT IGNORE INTO models(marca_id, nombre)
SELECT DISTINCT bm.id, TRIM(REPLACE(REPLACE(sd.modelo_nombre, CHAR(13), ''), CHAR(10), ''))
FROM staging_devices2 sd
JOIN brand_map bm ON bm.norm = LOWER(REPLACE(REPLACE(TRIM(sd.marca_nombre), CHAR(13), ''), CHAR(10), ''))
WHERE NULLIF(TRIM(sd.modelo_nombre),'') IS NOT NULL;

-- Update devices.model_id
UPDATE devices d
JOIN staging_devices2 sd ON sd.id = d.id
JOIN brand_map bm ON bm.norm = LOWER(REPLACE(REPLACE(TRIM(sd.marca_nombre), CHAR(13), ''), CHAR(10), ''))
JOIN models m ON m.marca_id = bm.id AND m.nombre = TRIM(REPLACE(REPLACE(sd.modelo_nombre, CHAR(13), ''), CHAR(10), ''))
SET d.model_id = m.id
WHERE d.model_id IS NULL;

-- Heuristic tipo_equipo on models
UPDATE models m JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'concentrador de oxígeno'
WHERE m.tipo_equipo IS NULL AND (
  UPPER(b.nombre) LIKE '%AIR SEP%' OR UPPER(b.nombre) LIKE '%DEVILBISS%' OR
  UPPER(m.nombre) REGEXP '(^|[^A-Z0-9])5L([^A-Z0-9]|$)|(^|[^A-Z0-9])525([^A-Z0-9]|$)|NEW LIFE'
);

UPDATE models m JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'oxímetro de pulso'
WHERE m.tipo_equipo IS NULL AND (
  UPPER(b.nombre) LIKE '%NELL%' OR UPPER(m.nombre) LIKE '%N-595%'
);

UPDATE models m JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'aspirador'
WHERE m.tipo_equipo IS NULL AND (
  UPPER(b.nombre) LIKE '%SILFAB%' AND UPPER(m.nombre) LIKE '%N-33%'
);

SET FOREIGN_KEY_CHECKS=1;
