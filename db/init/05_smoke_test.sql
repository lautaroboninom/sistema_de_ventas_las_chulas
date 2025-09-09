-- Actuamos como JEFE en esta sesión (RLS)
SET app.user_role='jefe';
-- Tomamos el id del admin seeded
SELECT set_config('app.user_id',
  COALESCE((SELECT id::text FROM users WHERE email='admin@example.com' LIMIT 1),'1'),
  true
);

-- 1) Cliente de prueba
INSERT INTO customers(razon_social, cod_empresa, telefono)
SELECT 'Cliente Demo','CLI001','011-0000'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE razon_social='Cliente Demo');

-- 2) Equipo de prueba (usa marcas/modelos seeded)
INSERT INTO devices(customer_id, marca_id, model_id, numero_serie, garantia_bool)
SELECT c.id, b.id, m.id, 'SN-DEMO-1', false
FROM customers c
JOIN marcas b ON b.nombre='BMC'
JOIN models m ON m.nombre='G3 AutoCPAP' AND m.marca_id=b.id
WHERE c.razon_social='Cliente Demo'
  AND NOT EXISTS (SELECT 1 FROM devices WHERE numero_serie='SN-DEMO-1');

-- 3) Ingreso de prueba (estado inicial = 'ingresado')
INSERT INTO ingresos(device_id, motivo, ubicacion_id, recibido_por, informe_preliminar)
SELECT d.id, 'reparación',
       (SELECT id FROM locations WHERE nombre='Taller'),
       (SELECT id FROM users WHERE email='admin@example.com'),
       'Ingreso de prueba'
FROM devices d
JOIN customers c ON c.id=d.customer_id
WHERE d.numero_serie='SN-DEMO-1'
  AND NOT EXISTS (SELECT 1 FROM ingresos t WHERE t.device_id = d.id);

-- 4) Obtener ingreso_id
WITH tid AS (
  SELECT t.id
  FROM ingresos t
  JOIN devices d ON d.id=t.device_id
  WHERE d.numero_serie='SN-DEMO-1'
  ORDER BY t.id DESC
  LIMIT 1
)
-- 5) Emitir presupuesto (sincroniza presupuesto_estado = 'emitido')
INSERT INTO quotes(ingreso_id, estado, subtotal, autorizado_por, forma_pago, fecha_emitido)
SELECT tid.id, 'emitido', 100000, 'Cliente', 'Transferencia', now()
FROM tid
ON CONFLICT (ingreso_id) DO UPDATE
SET estado=EXCLUDED.estado, subtotal=EXCLUDED.subtotal, fecha_emitido=EXCLUDED.fecha_emitido;

-- 6) Aprobar presupuesto (mueve ingreso a 'aprobado')
UPDATE quotes q
SET estado='aprobado', fecha_aprobado=now()
WHERE q.ingreso_id = (
  SELECT t.id FROM ingresos t
  JOIN devices d ON d.id=t.device_id
  WHERE d.numero_serie='SN-DEMO-1'
  ORDER BY t.id DESC LIMIT 1
);

-- 7) Chequeo rápido
SELECT t.id, t.estado, t.presupuesto_estado
FROM ingresos t
JOIN devices d ON d.id=t.device_id
WHERE d.numero_serie='SN-DEMO-1'
ORDER BY t.id DESC LIMIT 1;

-- 8) Proveedor externo demo y derivación
INSERT INTO proveedores_externos(nombre, contacto)
VALUES ('Proveedor Demo','contacto@proveedor.demo')
ON CONFLICT (nombre) DO NOTHING;

WITH tid AS (
  SELECT t.id
  FROM ingresos t
  JOIN devices d ON d.id=t.device_id
  WHERE d.numero_serie='SN-DEMO-1'
  ORDER BY t.id DESC LIMIT 1
),
pid AS (
  SELECT id FROM proveedores_externos WHERE nombre='Proveedor Demo' LIMIT 1
)
INSERT INTO equipos_derivados(ingreso_id, proveedor_id, remit_deriv, fecha_deriv, comentarios, estado)
SELECT tid.id, pid.id, 'R-0001', CURRENT_DATE, 'Derivación de prueba', 'derivado'
FROM tid, pid
ON CONFLICT DO NOTHING;

-- Reflejar estado del ingreso como hace la API
UPDATE ingresos t
SET estado='derivado'
WHERE t.id IN (SELECT ingreso_id FROM equipos_derivados ORDER BY id DESC LIMIT 1);

-- 9) Chequeo derivación (última por ingreso)
SELECT t.id, t.estado, ed.proveedor_id, pe.nombre proveedor, ed.fecha_deriv, ed.estado AS estado_derivacion
FROM ingresos t
JOIN LATERAL (
  SELECT e.* FROM equipos_derivados e
  WHERE e.ingreso_id = t.id
  ORDER BY e.fecha_deriv DESC, e.id DESC
  LIMIT 1
) ed ON TRUE
LEFT JOIN proveedores_externos pe ON pe.id = ed.proveedor_id
JOIN devices d ON d.id=t.device_id
WHERE d.numero_serie='SN-DEMO-1';
