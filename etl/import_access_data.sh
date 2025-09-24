# import_access_data.sh
#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_HOST:=127.0.0.1}"
: "${MYSQL_PORT:=3306}"
: "${MYSQL_USER:=sepid}"
: "${MYSQL_PASSWORD:=}"
: "${MYSQL_DATABASE:=servicio_tecnico}"

IN_DIR=${IN_DIR:-"etl/out"}

mysql_cli=( mysql --local-infile=1 -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
            -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" )

run_sql() { printf "%s;" "$1" | "${mysql_cli[@]}"; }

file_path() { cygpath -wa "$1" 2>/dev/null || realpath "$1"; }

echo "Importando datos Access desde $IN_DIR"
run_sql "SET NAMES utf8mb4"
run_sql "SET sql_log_bin=0"
run_sql "INSERT INTO locations (nombre) SELECT 'Estantería de Alquiler' FROM (SELECT 1) AS _tmp WHERE NOT EXISTS (SELECT 1 FROM locations WHERE LOWER(nombre) IN (LOWER('Estantería de Alquiler'), LOWER('Estanteria alquileres')))"

# =============== customers.csv (REPLACE) ===============
if [[ -f "$IN_DIR/customers.csv" ]]; then
  echo "Cargando customers.csv"
  fp=$(file_path "$IN_DIR/customers.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_customers;
CREATE TEMPORARY TABLE staging_customers (
  id INT,
  cod_empresa TEXT,
  razon_social TEXT,
  cuit TEXT,
  contacto TEXT,
  telefono TEXT,
  telefono_2 TEXT,
  email TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}'
INTO TABLE staging_customers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, cod_empresa, razon_social, cuit, contacto, telefono, telefono_2, email);
REPLACE INTO customers (id, cod_empresa, razon_social, cuit, contacto, telefono, telefono_2, email)
SELECT NULLIF(id,''), NULLIF(cod_empresa,''), razon_social, NULLIF(cuit,''), NULLIF(contacto,''), NULLIF(telefono,''), NULLIF(telefono_2,''), NULLIF(email,'') FROM staging_customers;
DROP TEMPORARY TABLE staging_customers;
SET FOREIGN_KEY_CHECKS=1;
SQL
else
  echo "WARN: no existe $IN_DIR/customers.csv"
fi

# =============== presupuestos_access.csv + reg_serv_costos_access.csv -> quotes/quote_items ===============
have_presu=false
have_regc=false
if [[ -f "$IN_DIR/presupuestos_access.csv" ]]; then have_presu=true; fi
if [[ -f "$IN_DIR/reg_serv_costos_access.csv" ]]; then have_regc=true; fi
if $have_presu || $have_regc; then
  echo "Construyendo quotes y quote_items desde Access"
  fp1=$(file_path "$IN_DIR/presupuestos_access.csv" 2>/dev/null || true)
  fp2=$(file_path "$IN_DIR/reg_serv_costos_access.csv" 2>/dev/null || true)
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
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
-- cargar si existe
SET @has_presu := ${have_presu} + 0;
IF @has_presu = 1 THEN
  LOAD DATA LOCAL INFILE '${fp1//\\/\\\\}' INTO TABLE staging_presup
  CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
  (ingreso_id, costo_cliente, costo_cliente2, fecha_emision, fecha_aprobado, forma_pago, mant_oferta, plazo_entrega, garant, altern2, emitido_por, presupuestado);
END IF;

DROP TEMPORARY TABLE IF EXISTS staging_regcost;
CREATE TEMPORARY TABLE staging_regcost (
  ingreso_id INT,
  costo_mano_obra TEXT,
  costo_repuestos TEXT,
  costo_total TEXT,
  autorizado_por TEXT
);
SET @has_regc := ${have_regc} + 0;
IF @has_regc = 1 THEN
  LOAD DATA LOCAL INFILE '${fp2//\\/\\\\}' INTO TABLE staging_regcost
  CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
  (ingreso_id, costo_mano_obra, costo_repuestos, costo_total, autorizado_por);
END IF;

-- Armar una vista temporal con los montos consolidados por ingreso
DROP TEMPORARY TABLE IF EXISTS staging_quotes_src;
CREATE TEMPORARY TABLE staging_quotes_src AS
SELECT 
  COALESCE(p.ingreso_id, r.ingreso_id) AS ingreso_id,
  -- subtotal preferente desde Registros (CostoTotal), si no, desde Presupuestos
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
FULL JOIN staging_regcost r ON r.ingreso_id = p.ingreso_id;

-- Cargar/actualizar quotes (id es AUTO_INCREMENT, clave natural es ingreso_id UNIQUE)
REPLACE INTO quotes (ingreso_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado)
SELECT s.ingreso_id, s.estado, 'ARS', CAST(NULLIF(s.subtotal_txt,'') AS DECIMAL(12,2)),
       NULLIF(s.autorizado_por,''), NULLIF(s.forma_pago,''),
       CASE WHEN NULLIF(s.fecha_emision,'')<>'' THEN STR_TO_DATE(s.fecha_emision, '%Y-%m-%d %H:%i:%s') ELSE NULL END,
       CASE WHEN NULLIF(s.fecha_aprobado,'')<>'' THEN STR_TO_DATE(s.fecha_aprobado, '%Y-%m-%d %H:%i:%s') ELSE NULL END
FROM staging_quotes_src s
JOIN ingresos i ON i.id = s.ingreso_id;

-- Regenerar items sintéticos por cada quote (mano_obra / repuesto) desde staging_regcost
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
SET FOREIGN_KEY_CHECKS=1;
SQL
fi

# =============== ingresos_textos_access.csv -> update textos de ingresos ===============
if [[ -f "$IN_DIR/ingresos_textos_access.csv" ]]; then
  echo "Actualizando textos de ingresos (descripcion/trabajos)"
  fp=$(file_path "$IN_DIR/ingresos_textos_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_ingresos_textos;
CREATE TEMPORARY TABLE staging_ingresos_textos (
  ingreso_id INT,
  descripcion_problema TEXT,
  piezas_reemplazadas TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_ingresos_textos
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(ingreso_id, descripcion_problema, piezas_reemplazadas);
-- set descripcion_problema si viene
UPDATE ingresos t JOIN staging_ingresos_textos s ON s.ingreso_id = t.id
SET t.descripcion_problema = NULLIF(s.descripcion_problema,'')
WHERE NULLIF(s.descripcion_problema,'') IS NOT NULL AND NULLIF(s.descripcion_problema,'') <> '';
-- append piezas reemplazadas a trabajos_realizados
UPDATE ingresos t JOIN staging_ingresos_textos s ON s.ingreso_id = t.id
SET t.trabajos_realizados = TRIM(CONCAT(COALESCE(t.trabajos_realizados,''),
                                  CASE WHEN NULLIF(s.piezas_reemplazadas,'') IS NOT NULL AND s.piezas_reemplazadas<>'' THEN
                                       CONCAT(CASE WHEN t.trabajos_realizados IS NULL OR t.trabajos_realizados='' THEN '' ELSE '\n' END,
                                              'Piezas reemplazadas: ', s.piezas_reemplazadas)
                                       ELSE '' END))
WHERE NULLIF(s.piezas_reemplazadas,'') IS NOT NULL AND s.piezas_reemplazadas<>'';
DROP TEMPORARY TABLE staging_ingresos_textos;
SQL
else
  echo "WARN: no existe $IN_DIR/ingresos_textos_access.csv"
fi

# =============== handoffs_access.csv -> handoffs (REPLACE) ===============
if [[ -f "$IN_DIR/handoffs_access.csv" ]]; then
  echo "Cargando handoffs_access.csv (facturación por NFactura)"
  fp=$(file_path "$IN_DIR/handoffs_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
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
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_handoffs_access
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
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
SET FOREIGN_KEY_CHECKS=1;
SQL
else
  echo "WARN: no existe $IN_DIR/handoffs_access.csv"
fi

# =============== marcas_access.csv -> marcas (INSERT IGNORE) ===============
if [[ -f "$IN_DIR/marcas_access.csv" ]]; then
  echo "Cargando marcas_access.csv"
  fp=$(file_path "$IN_DIR/marcas_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_marcas;
CREATE TEMPORARY TABLE staging_marcas ( nombre TEXT );
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_marcas
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES (nombre);
INSERT IGNORE INTO marcas(nombre)
SELECT DISTINCT NULLIF(TRIM(nombre),'') FROM staging_marcas WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_marcas;
SQL
else
  echo "WARN: no existe $IN_DIR/marcas_access.csv"
fi

# =============== models_access.csv -> models (INSERT IGNORE via join) ===============
if [[ -f "$IN_DIR/models_access.csv" ]]; then
  echo "Cargando models_access.csv"
  fp=$(file_path "$IN_DIR/models_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_models;
CREATE TEMPORARY TABLE staging_models ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_models
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES (marca_nombre, nombre);
INSERT IGNORE INTO models(marca_id, nombre)
SELECT b.id, s.nombre FROM staging_models s JOIN marcas b ON b.nombre = s.marca_nombre WHERE NULLIF(TRIM(s.nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_models;
SQL
else
  echo "WARN: no existe $IN_DIR/models_access.csv"
fi

# =============== proveedores_externos_access.csv -> proveedores_externos ===============
if [[ -f "$IN_DIR/proveedores_externos_access.csv" ]]; then
  echo "Cargando proveedores_externos_access.csv"
  fp=$(file_path "$IN_DIR/proveedores_externos_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_prov_ext;
CREATE TEMPORARY TABLE staging_prov_ext ( nombre TEXT, contacto TEXT );
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_prov_ext
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES (nombre, contacto);
INSERT IGNORE INTO proveedores_externos(nombre, contacto, telefono, email, direccion, notas)
SELECT NULLIF(TRIM(nombre),''), NULLIF(TRIM(contacto),'') , NULL, NULL, NULL, NULL
FROM staging_prov_ext WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_prov_ext;
SQL
else
  echo "WARN: no existe $IN_DIR/proveedores_externos_access.csv"
fi

# =============== devices_access.csv -> devices (REPLACE via joins) ===============
if [[ -f "$IN_DIR/devices_access.csv" ]]; then
  echo "Cargando devices_access.csv"
  fp=$(file_path "$IN_DIR/devices_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
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
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_devices_access
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, customer_cod_empresa, marca_nombre, modelo_nombre, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado);

REPLACE INTO devices (id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado)
SELECT s.id,
       c.id,
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
LEFT JOIN models m ON m.nombre = s.modelo_nombre AND m.marca_id = b.id;
DROP TEMPORARY TABLE staging_devices_access;
SET FOREIGN_KEY_CHECKS=1;
SQL
else
  echo "WARN: no existe $IN_DIR/devices_access.csv"
fi

# =============== ingresos_access.csv -> ingresos (REPLACE) ===============
if [[ -f "$IN_DIR/ingresos_access.csv" ]]; then
  echo "Cargando ingresos_access.csv"
  fp=$(file_path "$IN_DIR/ingresos_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
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
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_ingresos_access
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, device_id, estado, motivo, fecha_ingreso, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado);

REPLACE INTO ingresos (id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, ubicacion_id, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado)
SELECT
  s.id,
  s.device_id,
  CASE
    WHEN LOWER(TRIM(s.estado)) IN ('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado') THEN LOWER(TRIM(s.estado))
    WHEN TRIM(s.estado) IN ('6','06','006') THEN 'ingresado'
    WHEN LOWER(TRIM(s.estado)) = 'deposito' THEN 'ingresado'
    ELSE 'ingresado'
  END,
  s.motivo,
  CASE WHEN NULLIF(s.fecha_ingreso,'') <> '' THEN STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s') ELSE NULL END,
  COALESCE(CASE WHEN NULLIF(s.fecha_ingreso,'') <> '' THEN STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s') ELSE NULL END, NOW()),
  CASE
    WHEN @loc_stock IS NOT NULL AND (TRIM(s.estado) IN ('6','06','006') OR LOWER(TRIM(s.estado)) = 'deposito') THEN @loc_stock
    ELSE NULL
  END,
  NULLIF(s.informe_preliminar,''),
  NULLIF(s.accesorios,''),
  NULLIF(s.remito_ingreso,''),
  NULLIF(s.comentarios,''),
  NULLIF(s.propietario_nombre,''),
  NULLIF(s.propietario_contacto,''),
  CASE WHEN s.presupuesto_estado IN ('pendiente','emitido','aprobado','rechazado','presupuestado') THEN s.presupuesto_estado ELSE 'pendiente' END
FROM staging_ingresos_access s;
DROP TEMPORARY TABLE staging_ingresos_access;
SET FOREIGN_KEY_CHECKS=1;
SQL
else
  echo "WARN: no existe $IN_DIR/ingresos_access.csv"
fi

# =============== ingresos_estado_access.csv -> actualizar ubicacion/estado/resolucion ===============
if [[ -f "$IN_DIR/ingresos_estado_access.csv" ]]; then
  echo "Aplicando mapeo de ubicaciones/estados desde ingresos_estado_access.csv"
  fp=$(file_path "$IN_DIR/ingresos_estado_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
-- Asegurar ubicaciones base
INSERT INTO locations (nombre)
SELECT 'Taller' FROM (SELECT 1) AS _t WHERE NOT EXISTS (SELECT 1 FROM locations WHERE LOWER(nombre)=LOWER('Taller'));
INSERT INTO locations (nombre)
SELECT 'Estantería de Alquiler' FROM (SELECT 1) AS _t WHERE NOT EXISTS (SELECT 1 FROM locations WHERE LOWER(nombre) IN (LOWER('Estantería de Alquiler'), LOWER('Estanteria alquileres')));
INSERT INTO locations (nombre)
SELECT 'Desguace' FROM (SELECT 1) AS _t WHERE NOT EXISTS (SELECT 1 FROM locations WHERE LOWER(nombre)=LOWER('Desguace'));

DROP TEMPORARY TABLE IF EXISTS staging_ingresos_estado;
CREATE TEMPORARY TABLE staging_ingresos_estado (
  id INT,
  estado_num INT,
  entregado TEXT,
  alquilado TEXT,
  indic_presup TEXT,
  presupuestar TEXT,
  nu_presup TEXT,
  impresion_remito TEXT,
  impre_remito TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_ingresos_estado
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, estado_num, entregado, alquilado, indic_presup, presupuestar, nu_presup, impresion_remito, impre_remito);

-- IDs de ubicacion
SET @loc_taller := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('Taller') ORDER BY id ASC LIMIT 1);
SET @loc_estant := (
  SELECT id FROM locations 
   WHERE LOWER(nombre) IN (LOWER('Estantería de Alquiler'), LOWER('Estanteria alquileres'))
   ORDER BY (LOWER(nombre)=LOWER('Estantería de Alquiler')) DESC, id ASC LIMIT 1);
SET @loc_desguace := (SELECT id FROM locations WHERE LOWER(nombre)=LOWER('Desguace') ORDER BY id ASC LIMIT 1);

-- Ubicaciones segun estado_num
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.ubicacion_id = @loc_taller
 WHERE s.estado_num IN (1,2,3,4,5,7,9,10);

UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.ubicacion_id = @loc_estant
 WHERE s.estado_num = 6;

UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.ubicacion_id = @loc_desguace
 WHERE s.estado_num = 8;

-- Motivo para control urgente (10)
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.motivo = 'urgente control'
 WHERE s.estado_num = 10;

-- Estado con precedencia: mantener 'entregado' si ya lo está
-- 1/5/10 -> ingresado (si no entregado)
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.estado = 'ingresado'
 WHERE s.estado_num IN (1,5,10) AND t.estado <> 'entregado';

-- 2 -> reparar (si no entregado)
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.estado = 'reparar'
 WHERE s.estado_num = 2 AND t.estado <> 'entregado';

-- 3 -> reparado (si no entregado)
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.estado = 'reparado'
 WHERE s.estado_num = 3 AND t.estado <> 'entregado';

-- 4,7,9 -> liberado
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.estado = 'liberado'
 WHERE s.estado_num IN (4,7,9);

-- 6 Deposito: si entregado o alquilado en Access -> marcar entregado y device.alquilado=1
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.estado = 'entregado'
 WHERE s.estado_num = 6 AND (
   LOWER(TRIM(COALESCE(s.entregado,''))) IN ('1','-1','t','true','y','yes','si','s��','s') OR
   LOWER(TRIM(COALESCE(s.alquilado,''))) IN ('1','-1','t','true','y','yes','si','s��','s')
 );

UPDATE devices d
JOIN ingresos t ON t.device_id = d.id
JOIN staging_ingresos_estado s ON s.id = t.id
   SET d.alquilado = 1
 WHERE s.estado_num = 6 AND (
   LOWER(TRIM(COALESCE(s.entregado,''))) IN ('1','-1','t','true','y','yes','si','s��','s') OR
   LOWER(TRIM(COALESCE(s.alquilado,''))) IN ('1','-1','t','true','y','yes','si','s��','s')
 );

-- Resolucion segun reglas
-- 3 + liberado (aprox: flag entregado) -> resolucion reparado y presupuesto presupuestado
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.resolucion = 'reparado', t.presupuesto_estado = 'presupuestado'
 WHERE s.estado_num = 3 AND LOWER(TRIM(COALESCE(s.entregado,''))) IN ('1','-1','t','true','y','yes','si','s��','s');

-- 4 -> no_reparado
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.resolucion = 'no_reparado'
 WHERE s.estado_num = 4;

-- 7 -> presupuesto_rechazado y presupuesto presupuestado
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.resolucion = 'presupuesto_rechazado', t.presupuesto_estado = 'presupuestado'
 WHERE s.estado_num = 7;

-- 9 -> no_se_encontro_falla
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.resolucion = 'no_se_encontro_falla'
 WHERE s.estado_num = 9;

-- 8 Depo Esquiu -> disposicion para repuesto
UPDATE ingresos t JOIN staging_ingresos_estado s ON s.id=t.id
   SET t.disposicion = 'para_repuesto'
 WHERE s.estado_num = 8;

DROP TEMPORARY TABLE staging_ingresos_estado;
SET FOREIGN_KEY_CHECKS=1;
SQL
else
  echo "WARN: no existe $IN_DIR/ingresos_estado_access.csv"
fi

# =============== model_tipo_equipo_access.csv -> actualizar models.tipo_equipo ===============
if [[ -f "$IN_DIR/model_tipo_equipo_access.csv" ]]; then
  echo "Actualizando models.tipo_equipo desde model_tipo_equipo_access.csv"
  fp=$(file_path "$IN_DIR/model_tipo_equipo_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_model_tipo_equipo;
CREATE TEMPORARY TABLE staging_model_tipo_equipo (
  marca_nombre TEXT,
  modelo_nombre TEXT,
  tipo_equipo TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_model_tipo_equipo
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(marca_nombre, modelo_nombre, tipo_equipo);

UPDATE models m
JOIN marcas b ON b.id = m.marca_id
JOIN staging_model_tipo_equipo s ON LOWER(s.marca_nombre) = LOWER(b.nombre) AND LOWER(s.modelo_nombre) = LOWER(m.nombre)
   SET m.tipo_equipo = NULLIF(s.tipo_equipo,'')
 WHERE NULLIF(s.tipo_equipo,'') IS NOT NULL AND NULLIF(s.tipo_equipo,'') <> '';

DROP TEMPORARY TABLE staging_model_tipo_equipo;
SQL
else
  echo "WARN: no existe $IN_DIR/model_tipo_equipo_access.csv"
fi

# =============== ingresos_entrega_access.csv -> actualizar ingresos.fecha_entrega ===============
if [[ -f "$IN_DIR/ingresos_entrega_access.csv" ]]; then
  echo "Actualizando ingresos.fecha_entrega desde ingresos_entrega_access.csv"
  fp=$(file_path "$IN_DIR/ingresos_entrega_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_ingresos_entrega;
CREATE TEMPORARY TABLE staging_ingresos_entrega (
  ingreso_id INT,
  fecha_entrega TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_ingresos_entrega
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(ingreso_id, fecha_entrega);

UPDATE ingresos t
JOIN staging_ingresos_entrega s ON s.ingreso_id = t.id
   SET t.fecha_entrega = CASE WHEN NULLIF(s.fecha_entrega,'')<>'' THEN STR_TO_DATE(s.fecha_entrega, '%Y-%m-%d %H:%i:%s') ELSE NULL END
 WHERE NULLIF(s.fecha_entrega,'')<>'';

DROP TEMPORARY TABLE staging_ingresos_entrega;
SQL
else
  echo "WARN: no existe $IN_DIR/ingresos_entrega_access.csv"
fi

# =============== ingresos_alquiler_access.csv -> marcar flags de alquiler (sin cambiar estado) ===============
if [[ -f "$IN_DIR/ingresos_alquiler_access.csv" ]]; then
  echo "Actualizando flags de alquiler (ingresos/devices) desde ingresos_alquiler_access.csv"
  fp=$(file_path "$IN_DIR/ingresos_alquiler_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_ingresos_alquiler;
CREATE TEMPORARY TABLE staging_ingresos_alquiler (
  ingreso_id INT,
  alquilado_flag TEXT,
  recibe_alquiler TEXT,
  cargo_alquiler TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_ingresos_alquiler
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(ingreso_id, alquilado_flag, recibe_alquiler, cargo_alquiler);

-- Actualizar ingreso: set flag y datos, sin tocar estado
UPDATE ingresos t
JOIN staging_ingresos_alquiler s ON s.ingreso_id = t.id
   SET t.alquiler_a = NULLIF(s.recibe_alquiler,''),
       t.alquilado  = CASE WHEN LOWER(TRIM(COALESCE(s.alquilado_flag,''))) IN ('1','-1','t','true','y','yes','si','sí','s') OR NULLIF(s.recibe_alquiler,'')<>'' OR NULLIF(s.cargo_alquiler,'')<>'' THEN 1 ELSE t.alquilado END;

-- Reflejar en devices
UPDATE devices d
JOIN ingresos t ON t.device_id = d.id
JOIN staging_ingresos_alquiler s ON s.ingreso_id = t.id
   SET d.alquilado = CASE WHEN LOWER(TRIM(COALESCE(s.alquilado_flag,''))) IN ('1','-1','t','true','y','yes','si','sí','s') OR NULLIF(s.recibe_alquiler,'')<>'' OR NULLIF(s.cargo_alquiler,'')<>'' THEN 1 ELSE d.alquilado END;

DROP TEMPORARY TABLE staging_ingresos_alquiler;
SQL
else
  echo "WARN: no existe $IN_DIR/ingresos_alquiler_access.csv"
fi

# =============== equipos_derivados_access.csv -> equipos_derivados ===============
if [[ -f "$IN_DIR/equipos_derivados_access.csv" ]]; then
  echo "Cargando equipos_derivados_access.csv"
  fp=$(file_path "$IN_DIR/equipos_derivados_access.csv")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
DROP TEMPORARY TABLE IF EXISTS staging_derivados;
CREATE TEMPORARY TABLE staging_derivados (
  ingreso_id INT,
  proveedor_nombre TEXT,
  remit_deriv TEXT,
  fecha_deriv TEXT,
  fecha_entrega TEXT
);
LOAD DATA LOCAL INFILE '${fp//\\/\\\\}' INTO TABLE staging_derivados
CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\n' IGNORE 1 LINES
(ingreso_id, proveedor_nombre, remit_deriv, fecha_deriv, fecha_entrega);
INSERT INTO equipos_derivados (ingreso_id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega)
SELECT s.ingreso_id, p.id, NULLIF(s.remit_deriv,''), NULLIF(NULLIF(s.fecha_deriv,''), '0000-00-00'), NULLIF(NULLIF(s.fecha_entrega,''), '0000-00-00')
FROM staging_derivados s JOIN proveedores_externos p ON p.nombre = s.proveedor_nombre
ON DUPLICATE KEY UPDATE proveedor_id=VALUES(proveedor_id), remit_deriv=VALUES(remit_deriv), fecha_deriv=VALUES(fecha_deriv), fecha_entrega=VALUES(fecha_entrega);
DROP TEMPORARY TABLE staging_derivados;
SQL
else
  echo "WARN: no existe $IN_DIR/equipos_derivados_access.csv"
fi

# Ajuste de AUTO_INCREMENT de ingresos
"${mysql_cli[@]}" <<SQL
SET @cur := (SELECT IFNULL(MAX(id),0)+1 FROM ingresos);
SET @next := GREATEST(@cur, 27868);
SET @sql := CONCAT('ALTER TABLE ingresos AUTO_INCREMENT=', @next);
PREPARE s1 FROM @sql; EXECUTE s1; DEALLOCATE PREPARE s1;
SQL

run_sql "SET sql_log_bin=1"
echo "Importación Access completa"
