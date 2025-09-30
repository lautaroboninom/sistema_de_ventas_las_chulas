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

SET @cid := COALESCE((SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('RESPIFLOW') LIMIT 1),(SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('MIGRACION') LIMIT 1));
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre)=UPPER('SILFAB') LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id=@marca AND UPPER(nombre)=UPPER('N33') LIMIT 1), @modelo_default);
SET @fecha_ingreso='2025-09-26 00:00:00';

-- 28542 C028
SET @os_id=28542; SET @ns='C028'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- 28543 2790013
SET @os_id=28543; SET @ns='2790013'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- 28544 11-0312-03-A
SET @os_id=28544; SET @ns='11-0312-03-A'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- 28545 2790151
SET @os_id=28545; SET @ns='2790151'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

-- 28546 06-0117-11-A
SET @os_id=28546; SET @ns='06-0117-11-A'; SET @mg=NULL; SET @acc='';
INSERT INTO devices (customer_id,marca_id,model_id,numero_serie,garantia_bool,n_de_control) VALUES(@cid,@marca,@modelo,@ns,0,@mg);
SET @dev:=LAST_INSERT_ID();
INSERT INTO ingresos (id,device_id,motivo,ubicacion_id,recibido_por,asignado_a,informe_preliminar,accesorios,equipo_variante,propietario_nombre,propietario_contacto,propietario_doc,garantia_reparacion,fecha_ingreso)
SELECT @os_id,@dev,'otros',@loc_taller,@uid,NULL,'',@acc,NULL,NULL,NULL,NULL,0,@fecha_ingreso WHERE NOT EXISTS(SELECT 1 FROM ingresos WHERE id=@os_id);

COMMIT;
