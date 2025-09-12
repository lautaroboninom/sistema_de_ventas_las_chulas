-- versión/modos
SELECT @@version AS version, @@sql_mode AS sql_mode, @@time_zone AS tz, @@character_set_server AS charset, @@collation_server AS collation;

-- conteos
SELECT 'users' t, COUNT(*) c FROM users
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'marcas', COUNT(*) FROM marcas
UNION ALL SELECT 'models', COUNT(*) FROM models
UNION ALL SELECT 'locations', COUNT(*) FROM locations
UNION ALL SELECT 'devices', COUNT(*) FROM devices
UNION ALL SELECT 'ingresos', COUNT(*) FROM ingresos
UNION ALL SELECT 'quotes', COUNT(*) FROM quotes
UNION ALL SELECT 'quote_items', COUNT(*) FROM quote_items
UNION ALL SELECT 'proveedores_externos', COUNT(*) FROM proveedores_externos
UNION ALL SELECT 'equipos_derivados', COUNT(*) FROM equipos_derivados
UNION ALL SELECT 'ingreso_events', COUNT(*) FROM ingreso_events
UNION ALL SELECT 'handoffs', COUNT(*) FROM handoffs
UNION ALL SELECT 'password_reset_tokens', COUNT(*) FROM password_reset_tokens
UNION ALL SELECT 'audit_log', COUNT(*) FROM audit_log;

-- orfandad FKs (0 es OK; solo cuando la FK no es NULL y no existe el ref)
SELECT 'quotes.ingreso_id' k, COUNT(*) bad FROM quotes q LEFT JOIN ingresos i ON i.id=q.ingreso_id WHERE q.ingreso_id IS NOT NULL AND i.id IS NULL
UNION ALL SELECT 'quote_items.quote_id', COUNT(*) FROM quote_items qi LEFT JOIN quotes q ON q.id=qi.quote_id WHERE qi.quote_id IS NOT NULL AND q.id IS NULL
UNION ALL SELECT 'ingreso_events.ticket_id', COUNT(*) FROM ingreso_events e LEFT JOIN ingresos i ON i.id=e.ticket_id WHERE e.ticket_id IS NOT NULL AND i.id IS NULL
UNION ALL SELECT 'ingresos.device_id', COUNT(*) FROM ingresos t LEFT JOIN devices d ON d.id=t.device_id WHERE t.device_id IS NOT NULL AND d.id IS NULL
UNION ALL SELECT 'ingresos.ubicacion_id', COUNT(*) FROM ingresos t LEFT JOIN locations l ON l.id=t.ubicacion_id WHERE t.ubicacion_id IS NOT NULL AND l.id IS NULL
UNION ALL SELECT 'ingresos.asignado_a', COUNT(*) FROM ingresos t LEFT JOIN users u ON u.id=t.asignado_a WHERE t.asignado_a IS NOT NULL AND u.id IS NULL
UNION ALL SELECT 'ingresos.recibido_por', COUNT(*) FROM ingresos t LEFT JOIN users u ON u.id=t.recibido_por WHERE t.recibido_por IS NOT NULL AND u.id IS NULL
UNION ALL SELECT 'equipos_derivados.ingreso_id', COUNT(*) FROM equipos_derivados ed LEFT JOIN ingresos i ON i.id=ed.ingreso_id WHERE ed.ingreso_id IS NOT NULL AND i.id IS NULL
UNION ALL SELECT 'equipos_derivados.proveedor_id', COUNT(*) FROM equipos_derivados ed LEFT JOIN proveedores_externos p ON p.id=ed.proveedor_id WHERE ed.proveedor_id IS NOT NULL AND p.id IS NULL
UNION ALL SELECT 'handoffs.ingreso_id', COUNT(*) FROM handoffs h LEFT JOIN ingresos i ON i.id=h.ingreso_id WHERE h.ingreso_id IS NOT NULL AND i.id IS NULL
UNION ALL SELECT 'password_reset_tokens.user_id', COUNT(*) FROM password_reset_tokens t LEFT JOIN users u ON u.id=t.user_id WHERE t.user_id IS NOT NULL AND u.id IS NULL;

-- distintos de estado (diagnóstico rápido)
SELECT 'ingresos.estado' AS k, GROUP_CONCAT(DISTINCT estado ORDER BY estado SEPARATOR ',') AS vals FROM ingresos
UNION ALL SELECT 'ingresos.presupuesto_estado', GROUP_CONCAT(DISTINCT presupuesto_estado ORDER BY presupuesto_estado SEPARATOR ',') FROM ingresos
UNION ALL SELECT 'quotes.estado', GROUP_CONCAT(DISTINCT estado ORDER BY estado SEPARATOR ',') FROM quotes;
