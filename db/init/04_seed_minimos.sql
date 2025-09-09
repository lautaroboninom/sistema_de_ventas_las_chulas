-- Ubicaciones mínimas
INSERT INTO locations(nombre) VALUES
  ('Taller'),
  ('Estantería alquileres'),
  ('Depósito Sarmiento'),
  ('Depósito SEPID'),
  ('Depósito desguace')
ON CONFLICT (nombre) DO NOTHING;

-- Marcas de ejemplo
INSERT INTO marcas(nombre) VALUES
  ('BMC'), ('Longfian'), ('Magnamed'), ('Mindray'), ('Konsung')
ON CONFLICT (nombre) DO NOTHING;

-- Modelos de ejemplo (marca + modelo únicos por par)
INSERT INTO models(marca_id, nombre)
SELECT b.id, x.modelo
FROM (VALUES
  ('BMC','G3 AutoCPAP'),
  ('Longfian','JAY-10D'),
  ('Magnamed','Fleximag Max'),
  ('Mindray','iMEC 10'),
  ('Konsung','KSM-201')
) AS x(marca, modelo)
JOIN marcas b ON b.nombre = x.marca
ON CONFLICT (marca_id, nombre) DO NOTHING;

-- Usuario jefe inicial (cambiá el email/hash luego)
INSERT INTO users(nombre, email, hash_pw, rol, activo, perm_ingresar)
VALUES ('Administrador', 'admin@example.com', 'reemplazar_por_hash', 'jefe', true, true)
ON CONFLICT (email) DO NOTHING;

-- (Opcional) Semillar catálogo de proveedores desde histórico si existiera la tabla legacy
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='external_services'
  ) THEN
    INSERT INTO proveedores_externos(nombre)
    SELECT DISTINCT proveedor
    FROM external_services
    WHERE COALESCE(proveedor,'') <> ''
    ON CONFLICT (nombre) DO NOTHING;
  END IF;
END$$;
