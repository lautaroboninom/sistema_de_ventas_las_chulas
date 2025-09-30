-- mysql/patches/20250926_fix_sin_info_ingresos.sql
-- Corrige Marca/Modelo y Tipo de equipo para ingresos específicos cuando están en "Sin Información".
-- Idempotente y reutilizable: crea un procedimiento y lo invoca para los OS faltantes.

SET NAMES utf8mb4;
START TRANSACTION;

-- Asegurar marca/modelo por defecto "Sin Información"
INSERT INTO marcas (nombre) VALUES ('Sin Información')
  ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);
SET @marca_default := (SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('Sin Información') LIMIT 1);
INSERT INTO models (marca_id, nombre)
SELECT @marca_default, 'Sin Información'
WHERE NOT EXISTS (
  SELECT 1 FROM models WHERE marca_id=@marca_default AND UPPER(nombre)=UPPER('Sin Información')
);
SET @modelo_default := (SELECT id FROM models WHERE marca_id=@marca_default AND UPPER(nombre)=UPPER('Sin Información') LIMIT 1);

-- Helper: normalización básica para comparar nombres con/ sin espacios y guiones
DROP FUNCTION IF EXISTS norm_name;
DELIMITER $$
CREATE FUNCTION norm_name(s TEXT) RETURNS TEXT DETERMINISTIC
BEGIN
  IF s IS NULL THEN RETURN NULL; END IF;
  SET s = TRIM(s);
  SET s = REPLACE(s, ' ', ' '); -- NBSP a espacio
  SET s = REPLACE(s, '\n', '');
  SET s = REPLACE(s, '\r', '');
  SET s = REPLACE(s, ' ', '');
  SET s = REPLACE(s, '-', '');
  SET s = REPLACE(s, '.', '');
  RETURN UPPER(s);
END $$
DELIMITER ;

-- Procedimiento: fija marca/modelo/tipo para un ingreso dado
DROP PROCEDURE IF EXISTS fix_sin_info_by_id;
DELIMITER $$
CREATE PROCEDURE fix_sin_info_by_id(
  IN p_os_id INT,
  IN p_marca TEXT,
  IN p_modelo TEXT,
  IN p_tipo_equipo TEXT,
  IN p_numero_serie TEXT
)
proc: BEGIN
  DECLARE v_dev INT;
  DECLARE v_mid INT; -- marca id
  DECLARE v_moid INT; -- modelo id
  DECLARE v_def_mid INT;
  DECLARE v_def_moid INT;

  -- Defaults actuales
  SELECT id INTO v_def_mid FROM marcas WHERE UPPER(nombre)=UPPER('Sin Información') LIMIT 1;
  SELECT id INTO v_def_moid FROM models WHERE marca_id=v_def_mid AND UPPER(nombre)=UPPER('Sin Información') LIMIT 1;

  -- Ingreso -> device
  SELECT device_id INTO v_dev FROM ingresos WHERE id=p_os_id LIMIT 1;
  IF v_dev IS NULL THEN LEAVE proc; END IF;

  -- Resolver marca
  SELECT id INTO v_mid
  FROM marcas
  WHERE norm_name(nombre) = norm_name(p_marca)
  LIMIT 1;
  IF v_mid IS NULL THEN SET v_mid = v_def_mid; END IF;

  -- Resolver modelo (bajo la marca resuelta)
  SELECT id INTO v_moid
  FROM models
  WHERE marca_id = v_mid AND norm_name(nombre) = norm_name(p_modelo)
  LIMIT 1;
  IF v_moid IS NULL THEN SET v_moid = v_def_moid; END IF;

  -- Actualizar device sólo si hoy está sin info o NULL
  UPDATE devices d
  LEFT JOIN marcas mb ON mb.id = d.marca_id
  LEFT JOIN models mm ON mm.id = d.model_id
  SET d.marca_id = CASE WHEN d.marca_id IS NULL OR UPPER(COALESCE(mb.nombre,'')) = UPPER('Sin Información') THEN v_mid ELSE d.marca_id END,
      d.model_id = CASE WHEN d.model_id IS NULL OR UPPER(COALESCE(mm.nombre,'')) = UPPER('Sin Información') THEN v_moid ELSE d.model_id END
  WHERE d.id = v_dev;

  -- Serie / MG si viene y está vacío actualmente
  IF COALESCE(TRIM(p_numero_serie),'') <> '' THEN
    IF UPPER(p_numero_serie) LIKE 'MG %' THEN
      UPDATE devices SET n_de_control = COALESCE(NULLIF(n_de_control,''), TRIM(p_numero_serie))
      WHERE id=v_dev;
    ELSE
      UPDATE devices SET numero_serie = COALESCE(NULLIF(numero_serie,''), TRIM(p_numero_serie))
      WHERE id=v_dev;
    END IF;
  END IF;

  -- Tipo de equipo en el modelo (si está vacío y el modelo no es el default)
  IF v_moid IS NOT NULL AND v_moid <> v_def_moid AND COALESCE(TRIM(p_tipo_equipo),'') <> '' THEN
    UPDATE models SET tipo_equipo = TRIM(p_tipo_equipo)
    WHERE id = v_moid AND (tipo_equipo IS NULL OR TRIM(tipo_equipo) = '' OR UPPER(tipo_equipo) LIKE 'SIN INFORM%');
  END IF;

END proc $$
DELIMITER ;

-- Aplicar a OS faltantes que quedaron con "Sin Información"
-- 28531 24/09/25 ORTOPEDIA INTEGRAR CONCENTRADOR DE OXIGENO MG 1938 AIR SEP NEW LIFE
CALL fix_sin_info_by_id(28531, 'AIR SEP', 'NEW LIFE', 'CONCENTRADOR DE OXIGENO', 'MG 1938');

-- 28532 24/09/25 ORTOPEDIA INTEGRAR CONCENTRADOR DE OXIGENO MG 2231 AIR SEP NEW LIFE
CALL fix_sin_info_by_id(28532, 'AIR SEP', 'NEW LIFE', 'CONCENTRADOR DE OXIGENO', 'MG 2231');

-- 28535 24/09/25 RESPILIFE CPAP AUTO ES420507052 BMC G2S
CALL fix_sin_info_by_id(28535, 'BMC', 'G2S', 'CPAP AUTO', 'ES420507052');

-- 28524 18/09/25 BM MEDICAL CONCENTRADOR DE OXIGENO MG 4202 LONG FIAN JAY - 5
CALL fix_sin_info_by_id(28524, 'LONG FIAN', 'JAY - 5', 'CONCENTRADOR DE OXIGENO', 'MG 4202');

-- 28521 17/09/25 RESPIROXS CALENTADOR HUMIDIFICADOR D4-01031 MARBEL C-500-A
CALL fix_sin_info_by_id(28521, 'MARBEL', 'C-500-A', 'CALENTADOR HUMIDIFICADOR', 'D4-01031');

COMMIT;
