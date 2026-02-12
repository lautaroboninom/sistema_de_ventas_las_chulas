-- Marcas
DROP TEMPORARY TABLE IF EXISTS staging_marcas;
CREATE TEMPORARY TABLE staging_marcas ( nombre TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/marcas_access.csv'
INTO TABLE staging_marcas
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (nombre);
INSERT IGNORE INTO marcas(nombre)
SELECT DISTINCT NULLIF(TRIM(nombre),'') FROM staging_marcas WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_marcas;

-- Models
DROP TEMPORARY TABLE IF EXISTS staging_models;
CREATE TEMPORARY TABLE staging_models ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/models_access.csv'
INTO TABLE staging_models
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (marca_nombre, nombre);
INSERT IGNORE INTO models(marca_id, nombre)
SELECT b.id, TRIM(s.nombre)
FROM staging_models s JOIN marcas b ON b.nombre = TRIM(s.marca_nombre)
WHERE NULLIF(TRIM(s.nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_models;

-- Proveedores externos
DROP TEMPORARY TABLE IF EXISTS staging_prov_ext;
CREATE TEMPORARY TABLE staging_prov_ext ( nombre TEXT, contacto TEXT );
LOAD DATA LOCAL INFILE '/tmp/etl/proveedores_externos_access.csv'
INTO TABLE staging_prov_ext
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES (nombre, contacto);
INSERT IGNORE INTO proveedores_externos(nombre, contacto, telefono, email, direccion, notas)
SELECT NULLIF(TRIM(nombre),''), NULLIF(TRIM(contacto),'') , NULL, NULL, NULL, NULL
FROM staging_prov_ext WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_prov_ext;

-- Devices (id preservado)
-- Asegurar cliente placeholder para faltantes de CodEmpresa
INSERT INTO customers (cod_empresa, razon_social)
SELECT '__SIN_CE__', 'Sin CodEmpresa'
WHERE NOT EXISTS (
  SELECT 1 FROM customers WHERE cod_empresa='__SIN_CE__' AND razon_social='Sin CodEmpresa'
);
SET @cust_default := (SELECT id FROM customers WHERE cod_empresa='__SIN_CE__' ORDER BY id ASC LIMIT 1);
DROP TEMPORARY TABLE IF EXISTS staging_devices_access;
CREATE TEMPORARY TABLE staging_devices_access (
  id INT,
  customer_cod_empresa TEXT,
  marca_nombre TEXT,
  modelo_nombre TEXT,
  numero_serie TEXT,
  propietario TEXT,
  garantia_bool TEXT,
  etiq_garantia_ok TEXT,
  n_de_control TEXT,
  alquilado TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/devices_access.csv'
INTO TABLE staging_devices_access
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(id, customer_cod_empresa, marca_nombre, modelo_nombre, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado);

INSERT INTO devices (id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado)
SELECT s.id,
       COALESCE(c.id, @cust_default),
       b.id,
       m.id,
       NULLIF(s.numero_serie,''),
       NULLIF(s.propietario,''),
       CASE WHEN LOWER(TRIM(s.garantia_bool)) IN ('t','true','-1','1','y','yes','si','sí') THEN 1
            WHEN LOWER(TRIM(s.garantia_bool)) IN ('f','false','0','n','no') THEN 0
            ELSE NULL END,
       CASE WHEN LOWER(TRIM(s.etiq_garantia_ok)) IN ('t','true','-1','1','y','yes','si','sí','ok','x') THEN 1
            WHEN LOWER(TRIM(s.etiq_garantia_ok)) IN ('f','false','0','n','no') THEN 0
            ELSE NULL END,
       NULLIF(s.n_de_control,''),
       CASE WHEN LOWER(TRIM(s.alquilado)) IN ('t','true','-1','1','y','yes','si','sí') THEN 1
            WHEN LOWER(TRIM(s.alquilado)) IN ('f','false','0','n','no') THEN 0
            ELSE 0 END
FROM staging_devices_access s
LEFT JOIN customers c ON c.cod_empresa = s.customer_cod_empresa
LEFT JOIN marcas b ON b.nombre = s.marca_nombre
LEFT JOIN models m ON m.nombre = s.modelo_nombre AND m.marca_id = b.id
ON DUPLICATE KEY UPDATE
  customer_id=VALUES(customer_id),
  marca_id=VALUES(marca_id),
  model_id=VALUES(model_id),
  numero_serie=VALUES(numero_serie),
  propietario=VALUES(propietario),
  garantia_bool=VALUES(garantia_bool),
  etiq_garantia_ok=VALUES(etiq_garantia_ok),
  n_de_control=VALUES(n_de_control),
  alquilado=VALUES(alquilado);
DROP TEMPORARY TABLE staging_devices_access;

-- Ubicacion especial para stock de alquiler
INSERT INTO locations (nombre)
SELECT 'Estanteria alquileres'
WHERE NOT EXISTS (
  SELECT 1 FROM locations WHERE LOWER(nombre) = LOWER('Estanteria alquileres')
);

-- Ingresos
SET @loc_stock := (SELECT id FROM locations WHERE LOWER(nombre) = LOWER('Estanteria alquileres') ORDER BY id ASC LIMIT 1);
DROP TEMPORARY TABLE IF EXISTS staging_ingresos_access;
CREATE TEMPORARY TABLE staging_ingresos_access (
  id INT,
  device_id INT,
  estado TEXT,
  motivo TEXT,
  fecha_ingreso TEXT,
  informe_preliminar TEXT,
  accesorios TEXT,
  remito_ingreso TEXT,
  comentarios TEXT,
  propietario_nombre TEXT,
  propietario_contacto TEXT,
  presupuesto_estado TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/ingresos_access.csv'
INTO TABLE staging_ingresos_access
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(id, device_id, estado, motivo, fecha_ingreso, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado);

REPLACE INTO ingresos (id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, ubicacion_id, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado)
SELECT
  s.id,
  s.id,
  CASE
    WHEN LOWER(TRIM(s.estado)) IN ('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','baja','derivado','liberado','alquilado') THEN LOWER(TRIM(s.estado))
    WHEN TRIM(s.estado) IN ('6','06','006') THEN 'ingresado'
    WHEN LOWER(TRIM(s.estado)) IN ('deposito','depósito') THEN 'ingresado'
    ELSE 'ingresado'
  END,
  'otros',
  CASE WHEN NULLIF(s.fecha_ingreso,'') <> '' THEN STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s') ELSE NULL END,
    COALESCE(CASE WHEN NULLIF(s.fecha_ingreso,'') <> '' THEN STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s') ELSE NULL END, NOW()),
  CASE
    WHEN @loc_stock IS NOT NULL AND (TRIM(s.estado) IN ('6','06','006') OR LOWER(TRIM(s.estado)) IN ('deposito','depósito')) THEN @loc_stock
    ELSE NULL
  END,
  NULLIF(s.informe_preliminar,''),
  NULLIF(s.accesorios,''),
  NULLIF(s.remito_ingreso,''),
  NULLIF(s.comentarios,''),
  NULLIF(s.propietario_nombre,''),
  NULLIF(s.propietario_contacto,''),
  CASE WHEN s.presupuesto_estado IN ('pendiente','emitido','aprobado','rechazado','presupuestado') THEN s.presupuesto_estado ELSE 'pendiente' END
FROM staging_ingresos_access s
JOIN devices d ON d.id = s.id;
DROP TEMPORARY TABLE staging_ingresos_access;

-- Textos de ingresos
DROP TEMPORARY TABLE IF EXISTS staging_ingresos_textos;
CREATE TEMPORARY TABLE staging_ingresos_textos (
  ingreso_id INT,
  descripcion_problema TEXT,
  piezas_reemplazadas TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/ingresos_textos_access.csv'
INTO TABLE staging_ingresos_textos
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, descripcion_problema, piezas_reemplazadas);
UPDATE ingresos t JOIN staging_ingresos_textos s ON s.ingreso_id = t.id
SET t.descripcion_problema = NULLIF(s.descripcion_problema,'')
WHERE NULLIF(s.descripcion_problema,'') IS NOT NULL AND NULLIF(s.descripcion_problema,'') <> '';
UPDATE ingresos t JOIN staging_ingresos_textos s ON s.ingreso_id = t.id
SET t.trabajos_realizados = TRIM(CONCAT(COALESCE(t.trabajos_realizados,''),
                                  CASE WHEN NULLIF(s.piezas_reemplazadas,'') IS NOT NULL AND s.piezas_reemplazadas<>'' THEN
                                       CONCAT(CASE WHEN t.trabajos_realizados IS NULL OR t.trabajos_realizados='' THEN '' ELSE '\n' END,
                                              'Piezas reemplazadas: ', s.piezas_reemplazadas)
                                       ELSE '' END))
WHERE NULLIF(s.piezas_reemplazadas,'') IS NOT NULL AND s.piezas_reemplazadas<>'';
DROP TEMPORARY TABLE staging_ingresos_textos;

-- Presupuestos + registros (quotes + items)
DROP TEMPORARY TABLE IF EXISTS staging_presup;
CREATE TEMPORARY TABLE staging_presup (
  ingreso_id INT,
  costo_cliente TEXT,
  costo_cliente2 TEXT,
  fecha_emision TEXT,
  fecha_aprobado TEXT,
  forma_pago TEXT,
  mant_oferta TEXT,
  plazo_entrega TEXT,
  garant TEXT,
  altern2 TEXT,
  emitido_por TEXT,
  presupuestado TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/presupuestos_access.csv'
INTO TABLE staging_presup
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, costo_cliente, costo_cliente2, fecha_emision, fecha_aprobado, forma_pago, mant_oferta, plazo_entrega, garant, altern2, emitido_por, presupuestado);

DROP TEMPORARY TABLE IF EXISTS staging_regcost;
CREATE TEMPORARY TABLE staging_regcost (
  ingreso_id INT,
  costo_mano_obra TEXT,
  costo_repuestos TEXT,
  costo_total TEXT,
  autorizado_por TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/reg_serv_costos_access.csv'
INTO TABLE staging_regcost
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, costo_mano_obra, costo_repuestos, costo_total, autorizado_por);

DROP TEMPORARY TABLE IF EXISTS staging_quotes_src;
CREATE TEMPORARY TABLE staging_quotes_src AS
SELECT 
  COALESCE(p.ingreso_id, r.ingreso_id) AS ingreso_id,
  COALESCE(NULLIF(r.costo_total,''), NULLIF(p.costo_cliente2,''), NULLIF(p.costo_cliente,''), '0') AS subtotal_txt,
  p.forma_pago,
  p.fecha_emision,
  p.fecha_aprobado,
  r.autorizado_por,
  CASE 
    WHEN NULLIF(p.fecha_aprobado,'') IS NOT NULL AND p.fecha_aprobado <> '' THEN 'aprobado'
    WHEN NULLIF(p.fecha_emision,'') IS NOT NULL AND p.fecha_emision <> '' THEN 'emitido'
    WHEN LOWER(TRIM(COALESCE(p.presupuestado,''))) IN ('1','t','true','si','sí','y','yes') THEN 'presupuestado'
    ELSE 'pendiente'
  END AS estado
FROM staging_presup p
LEFT JOIN staging_regcost r ON r.ingreso_id = p.ingreso_id;

-- Evitar referenciar ingresos en el mismo statement que dispara trigger: usar copia temporal
DROP TEMPORARY TABLE IF EXISTS valid_ingresos;
CREATE TEMPORARY TABLE valid_ingresos AS SELECT id FROM ingresos;

REPLACE INTO quotes (ingreso_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado)
SELECT s.ingreso_id, s.estado, 'ARS', CAST(NULLIF(s.subtotal_txt,'') AS DECIMAL(12,2)),
       NULLIF(s.autorizado_por,''), NULLIF(s.forma_pago,''),
       CASE WHEN NULLIF(s.fecha_emision,'')<>'' THEN STR_TO_DATE(s.fecha_emision, '%Y-%m-%d %H:%i:%s') ELSE NULL END,
       CASE WHEN NULLIF(s.fecha_aprobado,'')<>'' THEN STR_TO_DATE(s.fecha_aprobado, '%Y-%m-%d %H:%i:%s') ELSE NULL END
FROM staging_quotes_src s JOIN valid_ingresos v ON v.id = s.ingreso_id;

DROP TEMPORARY TABLE IF EXISTS staging_quote_ids;
CREATE TEMPORARY TABLE staging_quote_ids AS
SELECT q.id AS quote_id, q.ingreso_id, r.costo_mano_obra, r.costo_repuestos
FROM quotes q LEFT JOIN staging_regcost r ON r.ingreso_id = q.ingreso_id;

DELETE qi FROM quote_items qi JOIN staging_quote_ids sq ON sq.quote_id = qi.quote_id;

INSERT INTO quote_items (quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
SELECT sq.quote_id, 'mano_obra', 'Mano de obra', 1, CAST(NULLIF(sq.costo_mano_obra,'') AS DECIMAL(12,2)), NULL
FROM staging_quote_ids sq
WHERE NULLIF(sq.costo_mano_obra,'') IS NOT NULL AND CAST(NULLIF(sq.costo_mano_obra,'') AS DECIMAL(12,2)) > 0;

INSERT INTO quote_items (quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
SELECT sq.quote_id, 'repuesto', 'Repuestos', 1, CAST(NULLIF(sq.costo_repuestos,'') AS DECIMAL(12,2)), NULL
FROM staging_quote_ids sq
WHERE NULLIF(sq.costo_repuestos,'') IS NOT NULL AND CAST(NULLIF(sq.costo_repuestos,'') AS DECIMAL(12,2)) > 0;

DROP TEMPORARY TABLE IF EXISTS staging_quote_ids;
DROP TEMPORARY TABLE IF EXISTS staging_quotes_src;
DROP TEMPORARY TABLE IF EXISTS staging_presup;
DROP TEMPORARY TABLE IF EXISTS staging_regcost;

-- Handoffs (facturación y remitos)
DROP TEMPORARY TABLE IF EXISTS staging_handoffs_access;
CREATE TEMPORARY TABLE staging_handoffs_access (
  ingreso_id INT,
  n_factura TEXT,
  factura_url TEXT,
  remito_impreso TEXT,
  fecha_impresion_remito TEXT,
  impresion_remito_url TEXT,
  orden_taller TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/handoffs_access.csv'
INTO TABLE staging_handoffs_access
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, n_factura, factura_url, remito_impreso, fecha_impresion_remito, impresion_remito_url, orden_taller);

REPLACE INTO handoffs (ingreso_id, n_factura, factura_url, remito_impreso, fecha_impresion_remito, impresion_remito_url, orden_taller)
SELECT s.ingreso_id,
       NULLIF(s.n_factura,''),
       NULLIF(s.factura_url,''),
       CASE WHEN LOWER(TRIM(s.remito_impreso)) IN ('1','t','true','y','yes','si','sí') THEN 1
            WHEN LOWER(TRIM(s.remito_impreso)) IN ('0','f','false','n','no') THEN 0
            ELSE NULL END,
       CASE WHEN NULLIF(s.fecha_impresion_remito,'')<>'' THEN STR_TO_DATE(s.fecha_impresion_remito, '%Y-%m-%d') ELSE NULL END,
       NULLIF(s.impresion_remito_url,''),
       NULLIF(s.orden_taller,'')
FROM staging_handoffs_access s
JOIN ingresos i ON i.id = s.ingreso_id;
DROP TEMPORARY TABLE staging_handoffs_access;

-- Derivados
DROP TEMPORARY TABLE IF EXISTS staging_derivados;
CREATE TEMPORARY TABLE staging_derivados (
  ingreso_id INT,
  proveedor_nombre TEXT,
  remit_deriv TEXT,
  fecha_deriv TEXT,
  fecha_entrega TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/equipos_derivados_access.csv'
INTO TABLE staging_derivados
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
IGNORE 1 LINES
(ingreso_id, proveedor_nombre, remit_deriv, fecha_deriv, fecha_entrega);
INSERT INTO equipos_derivados (ingreso_id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega)
SELECT s.ingreso_id, p.id, NULLIF(s.remit_deriv,''), NULLIF(NULLIF(s.fecha_deriv,''), '0000-00-00'), NULLIF(NULLIF(s.fecha_entrega,''), '0000-00-00')
FROM staging_derivados s JOIN proveedores_externos p ON p.nombre = s.proveedor_nombre
ON DUPLICATE KEY UPDATE proveedor_id=VALUES(proveedor_id), remit_deriv=VALUES(remit_deriv), fecha_deriv=VALUES(fecha_deriv), fecha_entrega=VALUES(fecha_entrega);
DROP TEMPORARY TABLE staging_derivados;

-- Ajuste de AUTO_INCREMENT
SET @cur := (SELECT IFNULL(MAX(id),0)+1 FROM ingresos);
SET @next := GREATEST(@cur, 27868);
SET @sql := CONCAT('ALTER TABLE ingresos AUTO_INCREMENT=', @next);
PREPARE s1 FROM @sql; EXECUTE s1; DEALLOCATE PREPARE s1;

