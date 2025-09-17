-- mysql/03_fkeys.sql
-- TODAS las FKs explícitas (sin REFERENCES inline). Idempotente.

-- Helper: función para agregar FK si no existe (usando información de information_schema)
-- Nota: MySQL no soporta procedural SQL aquí sin delimitadores; aplicamos patrón DROP/ADD condicional con consultas previas.

-- users: (sin FKs)

-- marcas → users
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints 
           WHERE constraint_schema = DATABASE() AND table_name='marcas' AND constraint_type='FOREIGN KEY' AND constraint_name='marcas_tecnico_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE marcas ADD CONSTRAINT marcas_tecnico_id_fkey FOREIGN KEY (tecnico_id) REFERENCES users(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- models → marcas, users
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='models' AND constraint_name='models_marca_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE models ADD CONSTRAINT models_marca_id_fkey FOREIGN KEY (marca_id) REFERENCES marcas(id) ON DELETE RESTRICT', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='models' AND constraint_name='models_tecnico_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE models ADD CONSTRAINT models_tecnico_id_fkey FOREIGN KEY (tecnico_id) REFERENCES users(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- devices → customers, marcas, models
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='devices' AND constraint_name='devices_customer_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE devices ADD CONSTRAINT devices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='devices' AND constraint_name='devices_marca_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE devices ADD CONSTRAINT devices_marca_id_fkey FOREIGN KEY (marca_id) REFERENCES marcas(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='devices' AND constraint_name='devices_model_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE devices ADD CONSTRAINT devices_model_id_fkey FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ingresos → devices, locations, users (asignado_a, recibido_por)
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingresos' AND constraint_name='ingresos_device_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingresos ADD CONSTRAINT ingresos_device_id_fkey FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE RESTRICT', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingresos' AND constraint_name='ingresos_ubicacion_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingresos ADD CONSTRAINT ingresos_ubicacion_id_fkey FOREIGN KEY (ubicacion_id) REFERENCES locations(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingresos' AND constraint_name='ingresos_asignado_a_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingresos ADD CONSTRAINT ingresos_asignado_a_fkey FOREIGN KEY (asignado_a) REFERENCES users(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingresos' AND constraint_name='ingresos_recibido_por_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingresos ADD CONSTRAINT ingresos_recibido_por_fkey FOREIGN KEY (recibido_por) REFERENCES users(id) ON DELETE SET NULL', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- quotes → ingresos
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='quotes' AND constraint_name='quotes_ingreso_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE quotes ADD CONSTRAINT quotes_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES ingresos(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- quote_items → quotes, repuestos (si existe)
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='quote_items' AND constraint_name='quote_items_quote_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE quote_items ADD CONSTRAINT quote_items_quote_id_fkey FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ingreso_events (legacy ticket_id) → ingresos
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingreso_events' AND constraint_name='ingreso_events_ticket_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingreso_events ADD CONSTRAINT ingreso_events_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES ingresos(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ingreso_media -> ingresos, users
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingreso_media' AND constraint_name='ingreso_media_ingreso_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingreso_media ADD CONSTRAINT ingreso_media_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES ingresos(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='ingreso_media' AND constraint_name='ingreso_media_usuario_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE ingreso_media ADD CONSTRAINT ingreso_media_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE RESTRICT', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- equipos_derivados → ingresos, proveedores_externos
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='equipos_derivados' AND constraint_name='equipos_derivados_ingreso_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE equipos_derivados ADD CONSTRAINT equipos_derivados_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES ingresos(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='equipos_derivados' AND constraint_name='equipos_derivados_proveedor_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE equipos_derivados ADD CONSTRAINT equipos_derivados_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES proveedores_externos(id) ON DELETE RESTRICT', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- handoffs → ingresos
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='handoffs' AND constraint_name='handoffs_ingreso_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE handoffs ADD CONSTRAINT handoffs_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES ingresos(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- password_reset_tokens → users
SET @t := (SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = DATABASE() AND table_name='password_reset_tokens' AND constraint_name='prt_user_id_fkey');
SET @sql := IF(@t=0, 'ALTER TABLE password_reset_tokens ADD CONSTRAINT prt_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE', 'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

