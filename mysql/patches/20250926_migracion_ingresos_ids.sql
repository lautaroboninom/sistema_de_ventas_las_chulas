-- mysql/patches/20250926_migracion_ingresos_ids.sql
-- MigraciÃ³n: creaciÃ³n de ingresos con IDs especÃ­ficos (para alinear OS con base anterior)
-- Incluye ingresos reales provistos y rellenos "bluff" para reservar nÃºmeros faltantes.
-- Idempotente (usa NOT EXISTS/ON DUPLICATE) y con fallbacks seguros.

START TRANSACTION;

-- Usuario receptor preferido: "Lautaro"; fallback a cualquier activo
SET @uid := (SELECT id FROM users WHERE LOWER(nombre) = LOWER('Lautaro') LIMIT 1);
SET @uid := COALESCE(
  @uid,
  (
    SELECT id FROM users
    WHERE activo = 1
    ORDER BY CASE WHEN rol IN ('jefe','admin') THEN 0 ELSE 1 END, id
    LIMIT 1
  )
);

-- UbicaciÃ³n por defecto: Taller
SET @loc_taller := (SELECT id FROM locations WHERE LOWER(nombre) = LOWER('Taller') LIMIT 1);

-- Marca/Modelo por defecto: "Sin InformaciÃ³n"
INSERT INTO marcas (nombre) VALUES ('Sin InformaciÃ³n')
  ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);
SET @marca_default := (SELECT id FROM marcas WHERE UPPER(nombre) = UPPER('Sin InformaciÃ³n') LIMIT 1);
INSERT INTO models (marca_id, nombre)
SELECT @marca_default, 'Sin InformaciÃ³n'
WHERE NOT EXISTS (
  SELECT 1 FROM models WHERE marca_id = @marca_default AND UPPER(nombre) = UPPER('Sin InformaciÃ³n')
);
SET @modelo_default := (SELECT id FROM models WHERE marca_id = @marca_default AND UPPER(nombre) = UPPER('Sin InformaciÃ³n') LIMIT 1);

-- Cliente por defecto para rellenos
INSERT INTO customers (razon_social, cod_empresa)
SELECT 'MIGRACION', 'MIG'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE UPPER(razon_social) = UPPER('MIGRACION'));
SET @cid_mig := (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('MIGRACION') LIMIT 1);

-- Helper: crea device y luego ingreso con ID fijo
-- Uso: define @cid, @marca_name, @modelo_name, @serie_raw, @fecha_ingreso, @os_id
--      el script resuelve marca/modelo; si no existen usa los defaults.
--      Si @serie_raw comienza con "MG ", se guarda como n_de_control (MG) y deja numero_serie NULL.

-- =========================================
-- Ingresos reales de la lista (excepto 28517 ya existente)
-- =========================================

-- 28522 â€¢ 17/09/2025 â€¢ RESPIROXS â€¢ MARBEL â€¢ C-500-A â€¢ E2*1902
SET @os_id = 28522; SET @fecha_ingreso = '2025-09-17 00:00:00';
SET @serie_raw = 'E2*1902';
SET @marca_name = 'MARBEL'; SET @modelo_name = 'C-500-A';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('RESPIROXS') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (
  id, device_id, motivo, ubicacion_id, recibido_por, asignado_a,
  informe_preliminar, accesorios, equipo_variante,
  propietario_nombre, propietario_contacto, propietario_doc,
  garantia_reparacion, fecha_ingreso
)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL,
       '', '', NULL,
       NULL, NULL, NULL,
       0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28520 â€¢ 17/09/2025 â€¢ MGBIO â€¢ RESMED â€¢ AIR START 10 â€¢ 221518340059
SET @os_id = 28520; SET @fecha_ingreso = '2025-09-17 00:00:00';
SET @serie_raw = '221518340059';
SET @marca_name = 'RESMED'; SET @modelo_name = 'AIR START 10';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('MGBIO') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28516 â€¢ 17/09/2025 â€¢ NOVAMED S.A. â€¢ KONSUNG â€¢ 9EB â€¢ MA23080040053
SET @os_id = 28516; SET @fecha_ingreso = '2025-09-17 00:00:00';
SET @serie_raw = 'MA23080040053';
SET @marca_name = 'KONSUNG'; SET @modelo_name = '9EB';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('NOVAMED S.A.') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28521 â€¢ 17/09/2025 â€¢ RESPIROXS â€¢ MARBEL â€¢ C-500-A â€¢ D4-01031
SET @os_id = 28521; SET @fecha_ingreso = '2025-09-17 00:00:00';
SET @serie_raw = 'D4-01031';
SET @marca_name = 'MARBEL'; SET @modelo_name = 'C-500-A';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('RESPIROXS') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28524 â€¢ 18/09/2025 â€¢ BM MEDICAL â€¢ LONG FIAN â€¢ JAY - 5 â€¢ MG 4202
SET @os_id = 28524; SET @fecha_ingreso = '2025-09-18 00:00:00';
SET @serie_raw = 'MG 4202';
SET @marca_name = 'LONG FIAN'; SET @modelo_name = 'JAY - 5';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('BM MEDICAL') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) IN (UPPER('LONG FIAN'), UPPER('LONGFIAN')) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND (UPPER(nombre) = UPPER('JAY - 5') OR UPPER(nombre) = UPPER('JAY-5')) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28526 â€¢ 23/09/2025 â€¢ GUSTAVO GONZALEZ â€¢ YUWELL â€¢ 9F-5 â€¢ 2002050022
SET @os_id = 28526; SET @fecha_ingreso = '2025-09-23 00:00:00';
SET @serie_raw = '2002050022';
SET @marca_name = 'YUWELL'; SET @modelo_name = '9F-5';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('GUSTAVO GONZALEZ') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28527 â€¢ 23/09/2025 â€¢ NOVOCARE S.R.L. â€¢ KANGAROO â€¢ 224 â€¢ MG 2875
SET @os_id = 28527; SET @fecha_ingreso = '2025-09-23 00:00:00';
SET @serie_raw = 'MG 2875';
SET @marca_name = 'KANGAROO'; SET @modelo_name = '224';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('NOVOCARE S.R.L.') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28529 â€¢ 23/09/2025 â€¢ NOVOCARE S.R.L. â€¢ BOMBA DE ALIMENTACION
SET @os_id = 28529; SET @fecha_ingreso = '2025-09-23 00:00:00';
SET @serie_raw = NULL; -- sin dato
SET @marca_name = 'Sin InformaciÃ³n'; SET @modelo_name = 'Sin InformaciÃ³n';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('NOVOCARE S.R.L.') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := NULL; SET @ns := NULL;
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28530 â€¢ 24/09/2025 â€¢ ORTOPEDIA INTEGRAR â€¢ LONG FIAN â€¢ JAY - 5 â€¢ MG 4987
SET @os_id = 28530; SET @fecha_ingreso = '2025-09-24 00:00:00';
SET @serie_raw = 'MG 4987';
SET @marca_name = 'LONG FIAN'; SET @modelo_name = 'JAY - 5';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('ORTOPEDIA INTEGRAR') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) IN (UPPER('LONG FIAN'), UPPER('LONGFIAN')) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND (UPPER(nombre) = UPPER('JAY - 5') OR UPPER(nombre) = UPPER('JAY-5')) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28531 â€¢ 24/09/2025 â€¢ ORTOPEDIA INTEGRAR â€¢ AIR SEP â€¢ (sin modelo) â€¢ MG 1938
SET @os_id = 28531; SET @fecha_ingreso = '2025-09-24 00:00:00';
SET @serie_raw = 'MG 1938';
SET @marca_name = 'AIR SEP'; SET @modelo_name = 'Sin InformaciÃ³n';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('ORTOPEDIA INTEGRAR') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28532 â€¢ 24/09/2025 â€¢ ORTOPEDIA INTEGRAR â€¢ AIR SEP â€¢ (sin modelo) â€¢ MG 2231
SET @os_id = 28532; SET @fecha_ingreso = '2025-09-24 00:00:00';
SET @serie_raw = 'MG 2231';
SET @marca_name = 'AIR SEP'; SET @modelo_name = 'Sin InformaciÃ³n';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('ORTOPEDIA INTEGRAR') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28535 â€¢ 24/09/2025 â€¢ RESPILIFE â€¢ BMC â€¢ G2S â€¢ ES420507052
SET @os_id = 28535; SET @fecha_ingreso = '2025-09-24 00:00:00';
SET @serie_raw = 'ES420507052';
SET @marca_name = 'BMC'; SET @modelo_name = 'AUTO CPAP G2S';
SET @cid = (SELECT id FROM customers WHERE UPPER(razon_social) = UPPER('RESPILIFE') LIMIT 1);
SET @cid = COALESCE(@cid, @cid_mig);
SET @marca := COALESCE((SELECT id FROM marcas WHERE UPPER(nombre) = UPPER(@marca_name) LIMIT 1), @marca_default);
-- Intentar jerÃ¡rquico cargado por patch: modelo puede existir como 'AUTO CPAP G2S'
SET @modelo := COALESCE((SELECT id FROM models WHERE marca_id = @marca AND UPPER(nombre) = UPPER(@modelo_name) LIMIT 1), @modelo_default);
SET @mg := (CASE WHEN UPPER(@serie_raw) LIKE 'MG %' THEN @serie_raw ELSE NULL END);
SET @ns := (CASE WHEN @mg IS NULL THEN @serie_raw ELSE NULL END);
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, '', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- =========================================
-- Rellenos (bluff) para reservar IDs faltantes
-- Faltan en rango 28516..28535: 28518, 28519, 28523, 28525, 28528, 28533, 28534
-- Se insertan como 'entregado' para no interferir con operativa.
-- =========================================

-- Helper comÃºn para rellenos
SET @marca := @marca_default; SET @modelo := @modelo_default; SET @cid := @cid_mig; SET @mg := NULL; SET @ns := NULL;

-- 28518 (fecha aprox: 2025-09-17)
SET @os_id = 28518; SET @fecha_ingreso = '2025-09-17 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28519 (fecha aprox: 2025-09-17)
SET @os_id = 28519; SET @fecha_ingreso = '2025-09-17 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28523 (fecha aprox: 2025-09-18)
SET @os_id = 28523; SET @fecha_ingreso = '2025-09-18 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28525 (fecha aprox: 2025-09-23)
SET @os_id = 28525; SET @fecha_ingreso = '2025-09-23 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28528 (fecha aprox: 2025-09-23)
SET @os_id = 28528; SET @fecha_ingreso = '2025-09-23 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28533 (fecha aprox: 2025-09-24)
SET @os_id = 28533; SET @fecha_ingreso = '2025-09-24 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- 28534 (fecha aprox: 2025-09-24)
SET @os_id = 28534; SET @fecha_ingreso = '2025-09-24 00:00:00';
INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
VALUES (@cid, @marca, @modelo, @ns, 0, @mg);
SET @dev := LAST_INSERT_ID();
INSERT INTO ingresos (id, device_id, motivo, ubicacion_id, recibido_por, asignado_a, informe_preliminar, accesorios, equipo_variante, propietario_nombre, propietario_contacto, propietario_doc, garantia_reparacion, fecha_ingreso, estado, fecha_entrega)
SELECT @os_id, @dev, 'otros', @loc_taller, @uid, NULL, 'relleno para conservar numeraciÃ³n', '', NULL, NULL, NULL, NULL, 0, @fecha_ingreso, 'entregado', @fecha_ingreso
WHERE NOT EXISTS (SELECT 1 FROM ingresos WHERE id = @os_id);

-- Ajustar el contador de AUTO_INCREMENT para que la prÃ³xima OS sea MAX(id)+1
SET @next_ai := (SELECT COALESCE(MAX(id), 0) + 1 FROM ingresos);
SET @sql := CONCAT('ALTER TABLE ingresos AUTO_INCREMENT = ', @next_ai);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

COMMIT;

-- Fin de script
