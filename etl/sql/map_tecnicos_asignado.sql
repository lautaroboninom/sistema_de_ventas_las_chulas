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

-- Mapear tecnicos a usuarios existentes (por nombre, roles aceptados)
DROP TEMPORARY TABLE IF EXISTS map_tecnico_usuario;
CREATE TEMPORARY TABLE map_tecnico_usuario AS
SELECT t.id_tecnico, u.id AS user_id
FROM staging_tecnicos t
JOIN users u ON LOWER(TRIM(u.nombre)) = LOWER(TRIM(t.nombre))
            AND u.rol IN ('tecnico','jefe','admin') AND u.activo = 1;

-- Actualizar ingresos.asignado_a cuando hay match
UPDATE ingresos i
JOIN staging_ing_empleado e ON e.ingreso_id = i.id
JOIN map_tecnico_usuario m ON m.id_tecnico = e.id_empleado
SET i.asignado_a = m.user_id;

SET FOREIGN_KEY_CHECKS=1;
