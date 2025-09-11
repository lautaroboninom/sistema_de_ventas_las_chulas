-- 08_seed.sql
-- Minimal, safe seed data. No secrets. Safe to re-run.

BEGIN;

-- Ubicaciones básicas
INSERT INTO public.locations(nombre) VALUES
  ('Taller'),
  ('Estantería alquileres'),
  ('Depósito Sarmiento'),
  ('Depósito SEPID'),
  ('Depósito desguace')
ON CONFLICT (nombre) DO NOTHING;

-- Marcas de ejemplo
INSERT INTO public.marcas(nombre) VALUES
  ('BMC'), ('Longfian'), ('Magnamed'), ('Mindray'), ('Konsung')
ON CONFLICT (nombre) DO NOTHING;

-- Modelos de ejemplo (marca + modelo únicos por par)
INSERT INTO public.models(marca_id, nombre)
SELECT b.id, x.modelo
FROM (VALUES
  ('BMC','G3 AutoCPAP'),
  ('Longfian','JAY-10D'),
  ('Magnamed','Fleximag Max'),
  ('Mindray','iMEC 10'),
  ('Konsung','KSM-201')
) AS x(marca, modelo)
JOIN public.marcas b ON b.nombre = x.marca
ON CONFLICT (marca_id, nombre) DO NOTHING;

-- Usuario inicial (cambie email/hash en entornos reales)
INSERT INTO public.users(nombre, email, hash_pw, rol, activo, perm_ingresar)
VALUES ('Administrador', 'admin@example.com', 'reemplazar_por_hash', 'jefe', true, true)
ON CONFLICT (email) DO NOTHING;

-- Catálogo de accesorios (ampliado) - idempotente
INSERT INTO public.catalogo_accesorios(nombre) VALUES
  ('cable220')
 ,('tubuladura PNI')
 ,('tubuladura')
 ,('cánula nasal')
 ,('cable ECG 5 der')
 ,('cable ECG 10 der')
 ,('sensor SpO2')
 ,('sensor de T')
 ,('cuff de PNI')
 ,('humidificador c/cámara')
 ,('humidificador s/cámara')
 ,('cable PI')
 ,('prolongador SpO2')
 ,('sensor proximal')
 ,('sensor distal')
 ,('brazo articulado')
 ,('tubuladura calefaccionada')
 ,('jarra')
 ,('fuente')
 ,('bolso')
 ,('kit respiratorio')
 ,('faja torácica')
 ,('conector faja torácica')
 ,('tarjeta SD')
 ,('tarjeta microSD')
 ,('manguera de O2')
 ,('manguera')
 ,('cable ECG 3 der')
 ,('electrodos ECG')
 ,('batería')
 ,('filtro HME')
 ,('filtro HEPA/antibacterial')
 ,('válvula PEEP')
 ,('máscara facial oxígeno')
 ,('máscara CPAP/BiPAP')
 ,('circuito respiratorio adulto')
 ,('circuito respiratorio pediátrico')
ON CONFLICT (nombre) DO NOTHING;

-- Opcional: seed de proveedores desde legacy external_services si existe
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='external_services'
  ) THEN
    INSERT INTO public.proveedores_externos(nombre)
    SELECT DISTINCT proveedor
    FROM public.external_services
    WHERE COALESCE(proveedor,'') <> ''
    ON CONFLICT (nombre) DO NOTHING;
  END IF;
END$$;

COMMIT;

