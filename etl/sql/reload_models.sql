DROP TEMPORARY TABLE IF EXISTS staging_models;
CREATE TEMPORARY TABLE staging_models ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/models_access.csv'
INTO TABLE staging_models
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (marca_nombre, nombre);
INSERT IGNORE INTO models(marca_id, nombre)
SELECT b.id, TRIM(s.nombre)
FROM staging_models s JOIN marcas b ON b.nombre = TRIM(s.marca_nombre)
WHERE NULLIF(TRIM(s.nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_models;
