-- mysql/02_indexes.sql
-- Índices no-PK (idempotente). MySQL no soporta DROP INDEX IF EXISTS.
-- Usar comprobación en information_schema para drop/create condicional.

-- marcas
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='marcas' AND index_name='idx_marcas_tecnico');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_marcas_tecnico ON marcas', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='marcas' AND index_name='idx_marcas_tecnico');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_marcas_tecnico ON marcas(tecnico_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- models
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='models' AND index_name='idx_models_marca');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_models_marca ON models', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='models' AND index_name='idx_models_marca');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_models_marca ON models(marca_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='models' AND index_name='idx_models_tecnico');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_models_tecnico ON models', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='models' AND index_name='idx_models_tecnico');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_models_tecnico ON models(tecnico_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- devices
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_customer');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_devices_customer ON devices', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_customer');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_devices_customer ON devices(customer_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_marca');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_devices_marca ON devices', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_marca');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_devices_marca ON devices(marca_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_model');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_devices_model ON devices', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_model');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_devices_model ON devices(model_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Numero de serie: usar prefijo válido para TEXT
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_nro_serie');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_devices_nro_serie ON devices', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='devices' AND index_name='idx_devices_nro_serie');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_devices_nro_serie ON devices (numero_serie(191))', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ingresos
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_device');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingresos_device ON ingresos', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_device');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingresos_device ON ingresos(device_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_estado');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingresos_estado ON ingresos', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_estado');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingresos_estado ON ingresos(estado)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_asignado');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingresos_asignado ON ingresos', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_asignado');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingresos_asignado ON ingresos(asignado_a)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_ubicacion');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingresos_ubicacion ON ingresos', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_ingresos_ubicacion');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingresos_ubicacion ON ingresos(ubicacion_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_vw_general_cliente_estado');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_vw_general_cliente_estado ON ingresos', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingresos' AND index_name='idx_vw_general_cliente_estado');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_vw_general_cliente_estado ON ingresos(estado, fecha_ingreso)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- quotes: (uq en ingreso_id ya creado)

-- quote_items
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='quote_items' AND index_name='idx_quote_items_quote');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_quote_items_quote ON quote_items', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='quote_items' AND index_name='idx_quote_items_quote');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_quote_items_quote ON quote_items(quote_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ingreso_events
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_events' AND index_name='idx_events_ingreso');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_events_ingreso ON ingreso_events', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_events' AND index_name='idx_events_ingreso');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_events_ingreso ON ingreso_events(ticket_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- equipos_derivados
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='equipos_derivados' AND index_name='idx_derivados_ingreso');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_derivados_ingreso ON equipos_derivados', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='equipos_derivados' AND index_name='idx_derivados_ingreso');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_derivados_ingreso ON equipos_derivados(ingreso_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='equipos_derivados' AND index_name='idx_derivados_proveedor');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_derivados_proveedor ON equipos_derivados', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='equipos_derivados' AND index_name='idx_derivados_proveedor');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_derivados_proveedor ON equipos_derivados(proveedor_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- audit_log
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_ts');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_audit_log_ts ON audit_log', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_ts');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_audit_log_ts ON audit_log(ts)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_path');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_audit_log_path ON audit_log', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_path');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_audit_log_path ON audit_log (path(191))', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_user');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_audit_log_user ON audit_log', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='audit_log' AND index_name='idx_audit_log_user');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_audit_log_user ON audit_log(user_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;



-- ingreso_media
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_media' AND index_name='idx_ingreso_media_ingreso_created');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingreso_media_ingreso_created ON ingreso_media', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_media' AND index_name='idx_ingreso_media_ingreso_created');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingreso_media_ingreso_created ON ingreso_media(ingreso_id, created_at DESC)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_media' AND index_name='idx_ingreso_media_usuario');
SET @sql := IF(@cnt>0, 'DROP INDEX idx_ingreso_media_usuario ON ingreso_media', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @cnt := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name='ingreso_media' AND index_name='idx_ingreso_media_usuario');
SET @sql := IF(@cnt=0, 'CREATE INDEX idx_ingreso_media_usuario ON ingreso_media(usuario_id)', 'DO 0'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
