SET NAMES utf8mb4;
START TRANSACTION;

SET @uid := (SELECT id FROM users WHERE LOWER(nombre)=LOWER('Lautaro') LIMIT 1);
SET @uid := COALESCE(@uid,(SELECT id FROM users WHERE activo=1 ORDER BY CASE WHEN rol IN ('jefe','admin') THEN 0 ELSE 1 END, id LIMIT 1));
SET @loc_taller := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('Taller') LIMIT 1);

INSERT INTO marcas (nombre) VALUES ('Sin Información') ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id);
SET @marca_default := (SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('Sin Información') LIMIT 1);
INSERT INTO models (marca_id,nombre)
SELECT @marca_default,'Sin Información'
WHERE NOT EXISTS(SELECT 1 FROM models WHERE marca_id=@marca_default AND UPPER(nombre)=UPPER('Sin Información'));
SET @modelo_default := (SELECT id FROM models WHERE marca_id=@marca_default AND UPPER(nombre)=UPPER('Sin Información') LIMIT 1);

INSERT INTO customers (razon_social,cod_empresa)
SELECT 'MIGRACION','MIG'
WHERE NOT EXISTS(SELECT 1 FROM customers WHERE UPPER(razon_social)=UPPER('MIGRACION'));
SET @cid_mig := (SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('MIGRACION') LIMIT 1);

-- AVIL SALUD SRL COVIDIEN PB 560
SET @cid := COALESCE((SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('AVIL SALUD SRL') LIMIT 1), @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('COVIDIEN') LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id=@marca AND UPPER(nombre)=UPPER('PB 560') LIMIT 1), @modelo_default);
SET @fecha_ingreso='2025-09-26 00:00:00';

-- 28537 40966F0001
SET @os_id=28537; SET @ns='40966F0001'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- 28538 40966F0527
SET @os_id=28538; SET @ns='40966F0527'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- SIED BMC G2S
SET @cid := COALESCE((SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('SIED') LIMIT 1), @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('BMC') LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id=@marca AND UPPER(nombre) IN (UPPER('G2S'), UPPER('AUTO CPAP G2S')) LIMIT 1), @modelo_default);
SET @fecha_ingreso='2025-09-26 00:00:00';

-- 28539 es1bda03611 + accesorios
SET @os_id=28539; SET @ns='es1bda03611'; SET @mg=NULL; SET @acc='TARJETA SD, SIN CAMARA HUMIDIFICADORA';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- SIED LONG FIAN JAY 5Q
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) IN (UPPER('LONG FIAN'), UPPER('LONGFIAN')) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id=@marca AND UPPER(nombre) IN (UPPER('JAY 5Q'), UPPER('JAY-5Q'), UPPER('JAY - 5Q'), UPPER('JAY 5')) LIMIT 1), @modelo_default);
SET @os_id=28540; SET @ns='MZJ5S5122203'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- MGBIO BMC G2S
SET @cid := COALESCE((SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('MGBIO') LIMIT 1), @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('BMC') LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id=@marca AND UPPER(nombre) IN (UPPER('G2S'), UPPER('AUTO CPAP G2S')) LIMIT 1), @modelo_default);
SET @fecha_ingreso='2025-09-25 00:00:00';
SET @os_id=28541; SET @ns='ES422615166'; SET @mg=NULL; SET @acc='FUENTE DE ALIMENTACION NS: 22500204056';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- Relleno por bug Access — 28536
SET @cid := @cid_mig; SET @marca := @marca_default; SET @modelo := @modelo_default; SET @ns=NULL; SET @mg=NULL; SET @acc='';
SET @fecha_ingreso='2025-09-25 00:00:00'; SET @os_id=28536;
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso,estado,fecha_entrega)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'relleno para conservar numeración (MIGRACIÓN faltante access)',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso,'entregado',@fecha_ingreso
WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

SET @next_ai := (SELECT COALESCE(MAX(id),0)+1 FROM ingresos);
SET @sql := CONCAT('ALTER TABLE ingresos AUTO_INCREMENT=', @next_ai);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

COMMIT;
