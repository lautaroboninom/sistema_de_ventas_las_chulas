START TRANSACTION;
UPDATE ingresos t
  LEFT JOIN devices d ON d.id=t.device_id
  SET t.device_id=NULL
  WHERE t.device_id IS NOT NULL AND d.id IS NULL;
UPDATE ingresos t
  LEFT JOIN locations l ON l.id=t.ubicacion_id
  SET t.ubicacion_id=NULL
  WHERE t.ubicacion_id IS NOT NULL AND l.id IS NULL;
UPDATE ingresos t
  LEFT JOIN users u ON u.id=t.asignado_a
  SET t.asignado_a=NULL
  WHERE t.asignado_a IS NOT NULL AND u.id IS NULL;
UPDATE ingresos t
  LEFT JOIN users u ON u.id=t.recibido_por
  SET t.recibido_por=NULL
  WHERE t.recibido_por IS NOT NULL AND u.id IS NULL;
COMMIT;
