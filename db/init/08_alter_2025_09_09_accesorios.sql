-- 08_alter_2025_09_09_accesorios.sql
-- Normalización de accesorios: catálogo + ítems por ingreso

BEGIN;

-- Catálogo de accesorios disponibles
CREATE TABLE IF NOT EXISTS public.catalogo_accesorios (
  id      serial PRIMARY KEY,
  nombre  text NOT NULL UNIQUE,
  activo  boolean NOT NULL DEFAULT true
);

-- Relación ingreso <-> accesorios (con referencia/nota)
CREATE TABLE IF NOT EXISTS public.ingreso_accesorios (
  id            serial PRIMARY KEY,
  ingreso_id    int NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
  accesorio_id  int NOT NULL REFERENCES public.catalogo_accesorios(id),
  referencia    text,
  descripcion   text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingreso_accesorios_ingreso ON public.ingreso_accesorios(ingreso_id);

-- Seed inicial (lista ampliada combinando los requeridos y accesorios comunes en equipamiento médico)
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

COMMIT;

