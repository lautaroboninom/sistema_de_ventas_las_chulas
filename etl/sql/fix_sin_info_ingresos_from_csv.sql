-- etl/sql/fix_sin_info_ingresos_from_csv.sql
-- Corrige en lote Marca/Modelo/Tipo de equipo para ingresos cuya marca/modelo actual está en "Sin Información" o NULL.
-- Fuente: un CSV con columnas: ingreso_id,marca,modelo,tipo,numero_serie
-- Colocar el CSV en una ruta accesible (ej: /tmp/fix_sin_info_ingresos.csv) y ajustar LOAD DATA abajo.
-- No crea marcas/modelos nuevos: si no existe en catálogo, deja "Sin Información".

SET NAMES utf8mb4;
START TRANSACTION;

-- Asegurar default "Sin Información"
INSERT INTO marcas (nombre) VALUES ('Sin Información')
  ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);
SET @def_marca := (SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('Sin Información') LIMIT 1);
INSERT INTO models (marca_id, nombre)
SELECT @def_marca, 'Sin Información'
WHERE NOT EXISTS (
  SELECT 1 FROM models WHERE marca_id=@def_marca AND UPPER(nombre)=UPPER('Sin Información')
);
SET @def_modelo := (SELECT id FROM models WHERE marca_id=@def_marca AND UPPER(nombre)=UPPER('Sin Información') LIMIT 1);

-- Normalizador de nombre (si no existe)
DROP FUNCTION IF EXISTS norm_name;
DELIMITER $$
CREATE FUNCTION norm_name(s TEXT) RETURNS TEXT DETERMINISTIC
BEGIN
  IF s IS NULL THEN RETURN NULL; END IF;
  SET s = TRIM(s);
  SET s = REPLACE(s, ' ', ' '); -- NBSP -> espacio
  SET s = REPLACE(s, '\n', '');
  SET s = REPLACE(s, '\r', '');
  SET s = REPLACE(s, ' ', '');
  SET s = REPLACE(s, '-', '');
  SET s = REPLACE(s, '.', '');
  RETURN UPPER(s);
END $$
DELIMITER ;

DROP TEMPORARY TABLE IF EXISTS tmp_fix_ingresos;
CREATE TEMPORARY TABLE tmp_fix_ingresos (
  ingreso_id INT NOT NULL,
  marca TEXT,
  modelo TEXT,
  tipo TEXT,
  numero_serie TEXT,
  KEY(ingreso_id)
);

-- Cargar datos desde CSV (copiar primero al contenedor MySQL en /tmp)
LOAD DATA LOCAL INFILE '/tmp/fix_sin_info_ingresos.csv'
INTO TABLE tmp_fix_ingresos
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, marca, modelo, tipo, numero_serie);

-- Mapas de catálogo normalizados
DROP TEMPORARY TABLE IF EXISTS brand_map;
CREATE TEMPORARY TABLE brand_map AS
SELECT id AS marca_id, nombre, norm_name(nombre) AS key_norm FROM marcas;

DROP TEMPORARY TABLE IF EXISTS model_map;
CREATE TEMPORARY TABLE model_map AS
SELECT id AS modelo_id, marca_id, nombre, norm_name(nombre) AS key_norm FROM models;

-- Resolver IDs esperados (si existen)
DROP TEMPORARY TABLE IF EXISTS tmp_fix_resolved;
CREATE TEMPORARY TABLE tmp_fix_resolved AS
SELECT f.ingreso_id,
       bm.marca_id AS new_marca_id,
       mm.modelo_id AS new_modelo_id,
       NULLIF(TRIM(f.tipo), '') AS tipo_equipo,
       NULLIF(TRIM(f.numero_serie), '') AS numero_serie
FROM tmp_fix_ingresos f
LEFT JOIN brand_map bm ON bm.key_norm = norm_name(f.marca)
LEFT JOIN model_map mm ON mm.marca_id = bm.marca_id AND mm.key_norm = norm_name(f.modelo);

-- Actualizar devices: sólo si hoy están en NULL o "Sin Información"
UPDATE devices d
JOIN ingresos t ON t.device_id = d.id
JOIN tmp_fix_resolved r ON r.ingreso_id = t.id
LEFT JOIN marcas mb ON mb.id = d.marca_id
LEFT JOIN models mo ON mo.id = d.model_id
SET d.marca_id = CASE
                   WHEN (d.marca_id IS NULL OR norm_name(COALESCE(mb.nombre,'')) = norm_name('Sin Informacion'))
                        AND r.new_marca_id IS NOT NULL THEN r.new_marca_id
                   ELSE d.marca_id
                 END,
    d.model_id = CASE
                   WHEN (d.model_id IS NULL OR mo.id = @def_modelo)
                        AND r.new_modelo_id IS NOT NULL THEN r.new_modelo_id
                   ELSE d.model_id
                 END,
    d.n_de_control = CASE
                       WHEN r.numero_serie IS NOT NULL AND UPPER(r.numero_serie) LIKE 'MG %' AND (d.n_de_control IS NULL OR d.n_de_control = '')
                         THEN TRIM(r.numero_serie)
                       ELSE d.n_de_control
                     END,
    d.numero_serie = CASE
                       WHEN r.numero_serie IS NOT NULL AND UPPER(r.numero_serie) NOT LIKE 'MG %' AND (d.numero_serie IS NULL OR d.numero_serie = '')
                         THEN TRIM(r.numero_serie)
                       ELSE d.numero_serie
                     END;

-- Completar tipo_equipo en el modelo (si existe y está vacío)
UPDATE models m
JOIN tmp_fix_resolved r ON r.new_modelo_id = m.id
SET m.tipo_equipo = r.tipo_equipo
WHERE r.tipo_equipo IS NOT NULL AND (m.tipo_equipo IS NULL OR TRIM(m.tipo_equipo) = '' OR UPPER(m.tipo_equipo) LIKE 'SIN INFORM%');

COMMIT;

-- Uso:
-- 1) Exporta un CSV con columnas: ingreso_id,marca,modelo,tipo,numero_serie
-- 2) Colócalo (por ejemplo) en /tmp/fix_sin_info_ingresos.csv
-- 3) Descomenta el LOAD DATA arriba con la ruta correcta
-- 4) Ejecuta este script
