SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_users;
CREATE TEMPORARY TABLE staging_users (
  id INT,
  nombre TEXT,
  email VARCHAR(320),
  hash_pw TEXT,
  rol TEXT,
  activo TEXT,
  creado_en TEXT,
  perm_ingresar TEXT
);
LOAD DATA INFILE '/var/lib/mysql-files/users.csv'
INTO TABLE staging_users
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, nombre, email, hash_pw, rol, activo, creado_en, perm_ingresar);
REPLACE INTO users (id, nombre, email, hash_pw, rol, activo, creado_en, perm_ingresar)
SELECT
  NULLIF(id,''),
  NULLIF(nombre,''),
  NULLIF(email,''),
  NULLIF(hash_pw,''),
  NULLIF(rol,''),
  CASE
    WHEN LOWER(TRIM(activo)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(activo)) IN ('f','false','0','n','no') THEN 0
    WHEN activo = '' THEN 1
    ELSE 0
  END,
  CASE WHEN creado_en = '' THEN NULL ELSE STR_TO_DATE(LEFT(creado_en, 19), '%Y-%m-%d %H:%i:%s') END,
  CASE
    WHEN LOWER(TRIM(perm_ingresar)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(perm_ingresar)) IN ('f','false','0','n','no') THEN 0
    WHEN perm_ingresar = '' THEN 0
    ELSE 0
  END
FROM staging_users;
DROP TEMPORARY TABLE staging_users;
SET FOREIGN_KEY_CHECKS=1;
