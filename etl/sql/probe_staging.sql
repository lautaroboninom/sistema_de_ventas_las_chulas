DROP TEMPORARY TABLE IF EXISTS staging_models;
CREATE TEMPORARY TABLE staging_models ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/models_access.csv'
INTO TABLE staging_models
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (marca_nombre, nombre);
SELECT COUNT(*) AS cnt_agilent FROM staging_models WHERE marca_nombre='AGILENT';
SELECT COUNT(*) AS cnt_trim_agilent FROM staging_models WHERE TRIM(marca_nombre)='AGILENT';
SELECT COUNT(*) AS sample_total FROM staging_models;
SELECT marca_nombre, HEX(SUBSTRING(marca_nombre,1,4)) FROM staging_models LIMIT 5;
DROP TEMPORARY TABLE staging_models;
