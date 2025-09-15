SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_devices;
CREATE TEMPORARY TABLE staging_devices (
  id INT,
  customer_id INT,
  marca_id INT,
  model_id INT,
  numero_serie TEXT,
  propietario TEXT,
  garantia_bool TEXT,
  etiq_garantia_ok TEXT,
  n_de_control TEXT,
  alquilado TEXT
);
LOAD DATA INFILE '/var/lib/mysql-files/devices.csv'
INTO TABLE staging_devices
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado);

REPLACE INTO devices (id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado)
SELECT
  NULLIF(id,''),
  NULLIF(customer_id,''),
  NULLIF(marca_id,''),
  NULLIF(model_id,''),
  NULLIF(numero_serie,''),
  NULLIF(propietario,''),
  CASE
    WHEN LOWER(TRIM(garantia_bool)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(garantia_bool)) IN ('f','false','0','n','no') THEN 0
    WHEN garantia_bool = '' THEN NULL
    ELSE NULL
  END,
  CASE
    WHEN LOWER(TRIM(etiq_garantia_ok)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(etiq_garantia_ok)) IN ('f','false','0','n','no') THEN 0
    WHEN etiq_garantia_ok = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(n_de_control,''),
  CASE
    WHEN LOWER(TRIM(alquilado)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(alquilado)) IN ('f','false','0','n','no') THEN 0
    WHEN alquilado = '' THEN 0
    ELSE 0
  END
FROM staging_devices;
DROP TEMPORARY TABLE staging_devices;
SET FOREIGN_KEY_CHECKS=1;

