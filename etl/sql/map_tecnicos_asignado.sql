SET FOREIGN_KEY_CHECKS=0;

DROP TEMPORARY TABLE IF EXISTS staging_tecnicos;
CREATE TEMPORARY TABLE staging_tecnicos (
  id_tecnico INT,
  nombre TEXT,
  baja TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/tecnicos_access.csv'
INTO TABLE staging_tecnicos
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (id_tecnico, nombre, baja);

DROP TEMPORARY TABLE IF EXISTS staging_ing_empleado;
CREATE TEMPORARY TABLE staging_ing_empleado (
  ingreso_id INT,
  id_empleado INT
);
LOAD DATA LOCAL INFILE '/tmp/etl/ingresos_empleado_access.csv'
INTO TABLE staging_ing_empleado
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (ingreso_id, id_empleado);

DROP TEMPORARY TABLE IF EXISTS tmp_users_norm;
CREATE TEMPORARY TABLE tmp_users_norm AS
SELECT
  u.id AS user_id,
  u.nombre,
  u.rol,
  u.activo,
  LOWER(TRIM(u.nombre)) COLLATE utf8mb4_unicode_ci AS norm_name,
  LOWER(REPLACE(TRIM(u.nombre), ' ', '')) COLLATE utf8mb4_unicode_ci AS norm_compact,
  LOWER(SUBSTRING_INDEX(TRIM(u.nombre), ' ', 1)) COLLATE utf8mb4_unicode_ci AS first_token
FROM users u
WHERE u.rol IN ('tecnico','jefe','admin','jefe_veedor','recepcion');

ALTER TABLE tmp_users_norm ADD PRIMARY KEY (user_id);

DROP TEMPORARY TABLE IF EXISTS tmp_unique_tokens;
CREATE TEMPORARY TABLE tmp_unique_tokens AS
SELECT first_token
FROM tmp_users_norm
GROUP BY first_token
HAVING COUNT(*) = 1;

DROP TEMPORARY TABLE IF EXISTS tmp_tecnicos_norm;
CREATE TEMPORARY TABLE tmp_tecnicos_norm AS
SELECT
  t.id_tecnico,
  t.nombre,
  t.baja,
  LOWER(TRIM(t.nombre)) COLLATE utf8mb4_unicode_ci AS norm_name,
  LOWER(REPLACE(TRIM(t.nombre), ' ', '')) COLLATE utf8mb4_unicode_ci AS norm_compact,
  LOWER(SUBSTRING_INDEX(TRIM(t.nombre), ' ', 1)) COLLATE utf8mb4_unicode_ci AS first_token
FROM staging_tecnicos t
WHERE t.id_tecnico IS NOT NULL AND t.id_tecnico <> 0;

DROP TEMPORARY TABLE IF EXISTS map_tecnico_usuario;
CREATE TEMPORARY TABLE map_tecnico_usuario (
  id_tecnico INT PRIMARY KEY,
  user_id INT
);

INSERT INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT id_tecnico, user_id
FROM (
  SELECT t.id_tecnico,
         u.user_id,
         ROW_NUMBER() OVER (
           PARTITION BY t.id_tecnico
           ORDER BY
             CASE WHEN u.rol = 'tecnico' THEN 0 WHEN u.rol IN ('jefe','admin','jefe_veedor') THEN 1 ELSE 2 END,
             CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
             u.user_id
         ) AS rn
  FROM tmp_tecnicos_norm t
  JOIN tmp_users_norm u ON t.norm_compact = u.norm_compact
) ranked
WHERE rn = 1;

DELETE FROM tmp_tecnicos_norm WHERE id_tecnico IN (SELECT id_tecnico FROM map_tecnico_usuario);

INSERT INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT id_tecnico, user_id
FROM (
  SELECT t.id_tecnico,
         u.user_id,
         ROW_NUMBER() OVER (
           PARTITION BY t.id_tecnico
           ORDER BY
             CASE WHEN u.rol = 'tecnico' THEN 0 WHEN u.rol IN ('jefe','admin','jefe_veedor') THEN 1 ELSE 2 END,
             CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
             u.user_id
         ) AS rn
  FROM tmp_tecnicos_norm t
  JOIN tmp_users_norm u ON t.norm_name = u.norm_name
) ranked
WHERE rn = 1;

DELETE FROM tmp_tecnicos_norm WHERE id_tecnico IN (SELECT id_tecnico FROM map_tecnico_usuario);

INSERT INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT id_tecnico, user_id
FROM (
  SELECT t.id_tecnico,
         u.user_id,
         ROW_NUMBER() OVER (
           PARTITION BY t.id_tecnico
           ORDER BY
             CASE WHEN u.rol = 'tecnico' THEN 0 WHEN u.rol IN ('jefe','admin','jefe_veedor') THEN 1 ELSE 2 END,
             CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
             u.user_id
         ) AS rn
  FROM tmp_tecnicos_norm t
  JOIN tmp_users_norm u ON t.first_token = u.first_token
  JOIN tmp_unique_tokens q ON q.first_token = u.first_token
) ranked
WHERE rn = 1;

DELETE FROM tmp_tecnicos_norm WHERE id_tecnico IN (SELECT id_tecnico FROM map_tecnico_usuario);

REPLACE INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT 8 AS id_tecnico,
       (
         SELECT u.user_id
         FROM tmp_users_norm u
         WHERE u.norm_compact = 'tecnicoexterno'
         ORDER BY CASE WHEN u.rol = 'tecnico' THEN 0 ELSE 1 END,
                  CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
                  u.user_id
         LIMIT 1
       ) AS user_id
FROM dual;

REPLACE INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT 10 AS id_tecnico,
       (
         SELECT u.user_id
         FROM tmp_users_norm u
         WHERE u.norm_compact LIKE 'ezequiel%'
         ORDER BY CASE WHEN u.rol = 'tecnico' THEN 0 ELSE 1 END,
                  CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
                  u.user_id
         LIMIT 1
       ) AS user_id
FROM dual;

REPLACE INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT 16 AS id_tecnico,
       (
         SELECT u.user_id
         FROM tmp_users_norm u
         WHERE u.first_token = 'tomas'
         ORDER BY CASE WHEN u.rol = 'tecnico' THEN 0 ELSE 1 END,
                  CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
                  u.user_id
         LIMIT 1
       ) AS user_id
FROM dual;

REPLACE INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT 6 AS id_tecnico,
       (
         SELECT u.user_id
         FROM tmp_users_norm u
         WHERE u.first_token = 'jorge'
         ORDER BY CASE WHEN u.rol = 'tecnico' THEN 0 ELSE 1 END,
                  CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
                  u.user_id
         LIMIT 1
       ) AS user_id
FROM dual;

REPLACE INTO map_tecnico_usuario (id_tecnico, user_id)
SELECT 1 AS id_tecnico,
       (
         SELECT u.user_id
         FROM tmp_users_norm u
         WHERE u.first_token = 'eduardo'
         ORDER BY CASE WHEN u.rol = 'tecnico' THEN 0 ELSE 1 END,
                  CASE WHEN u.activo = 1 THEN 0 ELSE 1 END,
                  u.user_id
         LIMIT 1
       ) AS user_id
FROM dual;

UPDATE ingresos i
JOIN staging_ing_empleado e ON e.ingreso_id = i.id
JOIN map_tecnico_usuario m ON m.id_tecnico = e.id_empleado
SET i.asignado_a = m.user_id;

SELECT t.id_tecnico, t.nombre, t.baja
FROM tmp_tecnicos_norm t
LEFT JOIN map_tecnico_usuario m ON m.id_tecnico = t.id_tecnico
WHERE m.id_tecnico IS NULL
ORDER BY t.id_tecnico;

SET FOREIGN_KEY_CHECKS=1;
