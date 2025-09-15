-- Conteos básicos
SELECT 'ingresos' AS tabla, COUNT(*) AS filas FROM ingresos
UNION ALL
SELECT 'devices', COUNT(*) FROM devices
UNION ALL
SELECT 'customers', COUNT(*) FROM customers
UNION ALL
SELECT 'marcas', COUNT(*) FROM marcas
UNION ALL
SELECT 'models', COUNT(*) FROM models;

-- Ingresos sin device
SELECT i.id FROM ingresos i LEFT JOIN devices d ON d.id = i.device_id WHERE d.id IS NULL LIMIT 50;

-- Devices sin customer
SELECT d.id FROM devices d LEFT JOIN customers c ON c.id = d.customer_id WHERE c.id IS NULL LIMIT 50;

-- Motivos fuera del ENUM (defensivo):
SELECT motivo, COUNT(*) FROM ingresos GROUP BY motivo;

-- Ingresos con N de factura pendiente de cargar (si se materializa handoffs luego)
-- SELECT i.id, h.n_factura FROM ingresos i LEFT JOIN handoffs h ON h.ingreso_id = i.id WHERE h.n_factura IS NOT NULL;

-- Próximo AUTO_INCREMENT de ingresos (debe ser >= 27868)
SHOW TABLE STATUS LIKE 'ingresos';

