SET @canon_name := 'Estantería de Alquiler';
-- Ensure canonical row exists
INSERT INTO locations (nombre)
SELECT @canon_name FROM (SELECT 1) AS _t WHERE NOT EXISTS (SELECT 1 FROM locations WHERE LOWER(nombre)=LOWER(@canon_name));
SET @canon_id := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER(@canon_name) ORDER BY id ASC LIMIT 1);

-- Alias candidates
SET @alias1_id := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('Estanteria alquileres') LIMIT 1);
SET @alias2_id := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('Estanteria de Alquiler') LIMIT 1);

-- Repoint ingresos to canonical id
UPDATE ingresos SET ubicacion_id=@canon_id WHERE ubicacion_id IS NOT NULL AND (ubicacion_id=@alias1_id OR ubicacion_id=@alias2_id);

-- Drop alias rows if different from canonical
DELETE FROM locations WHERE id IS NOT NULL AND id<>@canon_id AND (id=@alias1_id OR id=@alias2_id);

-- Show result
SELECT id, nombre FROM locations ORDER BY id;
