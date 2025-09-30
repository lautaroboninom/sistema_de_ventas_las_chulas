-- Setear estado 'liberado' para los 40 no-entregados provistos y registrar evento
DROP TEMPORARY TABLE IF EXISTS tmp_to_lib;
CREATE TEMPORARY TABLE tmp_to_lib (
  id INT PRIMARY KEY,
  de_estado VARCHAR(32) NULL
) ENGINE=Memory;

INSERT INTO tmp_to_lib(id, de_estado)
SELECT t.id, t.estado
FROM ingresos t
WHERE t.id IN (
27122,27494,27509,27637,26773,27536,27935,27998,27069,28053,
28074,28075,28079,27369,27229,28147,28200,28159,28228,28229,
28234,28235,28221,28273,28251,28393,28400,28259,28455,28460,
28399,28514,28473,28478,28479,28480,28488,28487,28484,28513
);

-- Actualizar estado
UPDATE ingresos t
JOIN tmp_to_lib s ON s.id = t.id
SET t.estado = 'liberado'
WHERE t.estado <> 'liberado';

-- Registrar evento de estado
INSERT INTO ingreso_events (ticket_id, de_estado, a_estado, ts, comentario)
SELECT s.id, s.de_estado, 'liberado', NOW(), 'Migración: marcado como listo para retiro'
FROM tmp_to_lib s;

DROP TEMPORARY TABLE IF EXISTS tmp_to_lib;
