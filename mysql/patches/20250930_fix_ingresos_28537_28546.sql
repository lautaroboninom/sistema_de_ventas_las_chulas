SET NAMES utf8mb4;
START TRANSACTION;

-- Tipos de equipo por modelo (idempotente)
UPDATE models m
JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'ASPIRADOR'
WHERE UPPER(b.nombre) = UPPER('SILFAB') AND UPPER(m.nombre) = UPPER('N33')
  AND (m.tipo_equipo IS NULL OR UPPER(m.tipo_equipo) LIKE 'SIN INFORM%');

UPDATE models m
JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'RESPIRADOR'
WHERE UPPER(b.nombre) = UPPER('COVIDIEN') AND UPPER(m.nombre) = UPPER('PB 560')
  AND (m.tipo_equipo IS NULL OR UPPER(m.tipo_equipo) LIKE 'SIN INFORM%');

UPDATE models m
JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'CPAP AUTO'
WHERE UPPER(b.nombre) = UPPER('BMC') AND UPPER(m.nombre) IN (UPPER('G2S'), UPPER('AUTO CPAP G2S'))
  AND (m.tipo_equipo IS NULL OR UPPER(m.tipo_equipo) LIKE 'SIN INFORM%');

UPDATE models m
JOIN marcas b ON b.id = m.marca_id
SET m.tipo_equipo = 'CONCENTRADOR DE OXIGENO'
WHERE UPPER(b.nombre) IN (UPPER('LONG FIAN'), UPPER('LONGFIAN'))
  AND UPPER(m.nombre) IN (UPPER('JAY 5Q'), UPPER('JAY-5Q'), UPPER('JAY - 5Q'), UPPER('JAY 5'), UPPER('JAY - 5'))
  AND (m.tipo_equipo IS NULL OR UPPER(m.tipo_equipo) LIKE 'SIN INFORM%');

-- Accesorios desde Access si están vacíos
UPDATE ingresos SET accesorios = 'C/TARJETA SD' WHERE id = 28535 AND (accesorios IS NULL OR TRIM(accesorios) = '');
UPDATE ingresos SET accesorios = 'TARJETA SD, SIN CAMARA HUMIDIFICADORA' WHERE id = 28539 AND (accesorios IS NULL OR TRIM(accesorios) = '');
UPDATE ingresos SET accesorios = 'FUENTE DE ALIMENTACION NS: 22500204056' WHERE id = 28541 AND (accesorios IS NULL OR TRIM(accesorios) = '');

COMMIT;

