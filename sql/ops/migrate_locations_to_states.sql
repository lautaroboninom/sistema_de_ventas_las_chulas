-- Normaliza ubicaciones usadas como proxy de estado.
-- - Desguace -> estado=baja, ubicacion='-'
-- - Alquilado -> estado=alquilado, ubicacion='-'
DO $$
DECLARE
  v_id_dash INTEGER;
  v_id_desguace INTEGER;
  v_id_alquilado INTEGER;
BEGIN
  -- Asegurar placeholder '-'
  INSERT INTO locations(nombre) VALUES ('-')
    ON CONFLICT (nombre) DO NOTHING;

  SELECT id INTO v_id_dash FROM locations WHERE nombre = '-' LIMIT 1;
  SELECT id INTO v_id_desguace FROM locations WHERE LOWER(nombre) = LOWER('Desguace') LIMIT 1;
  SELECT id INTO v_id_alquilado FROM locations WHERE LOWER(nombre) = LOWER('Alquilado') LIMIT 1;

  IF v_id_dash IS NULL THEN
    RAISE NOTICE 'No se pudo obtener id de ubicacion "-"';
  ELSE
    IF v_id_desguace IS NOT NULL THEN
      UPDATE ingresos SET estado='baja', ubicacion_id = v_id_dash WHERE ubicacion_id = v_id_desguace;
      UPDATE devices SET ubicacion_id = v_id_dash WHERE ubicacion_id = v_id_desguace;
      DELETE FROM locations WHERE id = v_id_desguace;
    END IF;
    IF v_id_alquilado IS NOT NULL THEN
      UPDATE ingresos SET estado='alquilado', ubicacion_id = v_id_dash WHERE ubicacion_id = v_id_alquilado;
      UPDATE devices SET ubicacion_id = v_id_dash WHERE ubicacion_id = v_id_alquilado;
      DELETE FROM locations WHERE id = v_id_alquilado;
    END IF;
  END IF;
END $$;
