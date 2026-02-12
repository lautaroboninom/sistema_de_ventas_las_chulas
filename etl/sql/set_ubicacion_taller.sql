UPDATE ingresos SET ubicacion_id=(SELECT id FROM locations WHERE LOWER(nombre)=LOWER('taller') LIMIT 1) WHERE ubicacion_id IS NULL;
