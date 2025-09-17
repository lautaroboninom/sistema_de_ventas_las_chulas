-- mysql/05_smoke_test.sql
-- Smoke básico: crea ingreso, emite y aprueba presupuesto, verifica transiciones

SET NAMES utf8mb4;

-- Seed mínimo de usuarios
INSERT INTO users(nombre,email,rol,activo)
VALUES ('Admin','admin@example.com','admin',true)
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);

INSERT INTO users(nombre,email,rol,activo)
VALUES ('Tecnico','tech@example.com','tecnico',true)
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);

-- Catálogos mínimos
INSERT INTO marcas(nombre) VALUES ('DemoBrand')
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);

INSERT INTO models(marca_id, nombre) 
SELECT id, 'DemoModel' FROM marcas WHERE nombre='DemoBrand'
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);

INSERT INTO customers(razon_social) VALUES ('Cliente Demo')
ON DUPLICATE KEY UPDATE razon_social=VALUES(razon_social);

-- Device
INSERT INTO devices(customer_id, marca_id, model_id, numero_serie)
SELECT c.id, b.id, m.id, 'SN-TEST-001'
FROM customers c, marcas b, models m
WHERE c.razon_social='Cliente Demo' AND b.nombre='DemoBrand' AND m.nombre='DemoModel'
LIMIT 1;

-- Ingreso
INSERT INTO ingresos(device_id, motivo, estado, ubicacion_id, asignado_a, informe_preliminar)
SELECT d.id, 'reparación', 'ingresado', l.id, NULL, 'Smoke test'
FROM devices d, locations l
WHERE d.numero_serie='SN-TEST-001' AND l.nombre='Taller'
LIMIT 1;

SET @ing := (SELECT id FROM ingresos ORDER BY id DESC LIMIT 1);

SET @tech := (SELECT id FROM users WHERE email='tech@example.com' LIMIT 1);
INSERT INTO ingreso_media(ingreso_id, usuario_id, storage_path, thumbnail_path, original_name, mime_type, size_bytes, width, height, comentario)
SELECT @ing, @tech, 'smoke/test.jpg', 'smoke/test_thumb.jpg', 'smoke.jpg', 'image/jpeg', 1024, 100, 100, 'smoke test'
FROM DUAL
WHERE @tech IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ingreso_media WHERE ingreso_id=@ing);

-- Quote emitida
INSERT INTO quotes(ingreso_id, estado, subtotal, autorizado_por, forma_pago, fecha_emitido)
VALUES (@ing, 'emitido', 1000.00, 'Cliente', '30 F.F.', NOW())
ON DUPLICATE KEY UPDATE estado='emitido', subtotal=1000.00, fecha_emitido=NOW();

-- Ítem de quote
INSERT INTO quote_items(quote_id, tipo, descripcion, qty, precio_u)
SELECT q.id, 'repuesto', 'Pieza X', 1.00, 1000.00
FROM quotes q WHERE q.ingreso_id=@ing
LIMIT 1;

-- Aprobar
UPDATE quotes SET estado='aprobado', fecha_aprobado=NOW()
WHERE ingreso_id=@ing;

-- Reporte
SELECT 
  'OK_SMOKE' AS status,
  (SELECT estado FROM ingresos WHERE id=@ing) AS ingreso_estado,
  (SELECT presupuesto_estado FROM ingresos WHERE id=@ing) AS ingreso_presupuesto_estado,
  (SELECT estado FROM quotes WHERE ingreso_id=@ing) AS quote_estado,
  (SELECT COUNT(*) FROM ingreso_events WHERE ticket_id=@ing) AS eventos_count;

