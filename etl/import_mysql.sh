#import_mysql.sh
#!/usr/bin/env bash
set -euo pipefail

# Importa CSV a MySQL usando LOAD DATA LOCAL INFILE
# Seguridad: LOCAL requiere local_infile=ON en cliente y servidor. 
# Asegurate de habilitarlo sólo para esta operación.

: "${MYSQL_HOST:=127.0.0.1}"
: "${MYSQL_PORT:=3306}"
: "${MYSQL_USER:=sepid}"
: "${MYSQL_PASSWORD:=}"  # no hardcodear en repo
: "${MYSQL_DATABASE:=servicio_tecnico}"

IN_DIR=${IN_DIR:-"etl/out"}

mysql_cli=( mysql --local-infile=1 -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
            -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" )

run_sql() {
  echo "SQL> $1" >&2
  printf "%s;" "$1" | "${mysql_cli[@]}"
}

load_csv() {
  local table="$1"
  local file="$IN_DIR/$table.csv"
  if [[ ! -f "$file" ]]; then
    echo "WARN: no existe $file, se omite $table" >&2
    return 0
  fi
  echo "Importando $file -> $table"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE $table
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# Carga con mapeo de booleanos desde CSV (t/f, true/false, 1/0) -> 1/0
# Solo para tabla users (impacta en login). Evita que 't' se importe como 0 en MySQL.
load_users_csv() {
  local table="users"
  local file="$IN_DIR/$table.csv"
  if [[ ! -f "$file" ]]; then
    echo "WARN: no existe $file, se omite $table" >&2
    return 0
  fi
  echo "Importando (booleans mapeados) $file -> $table"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_users;
CREATE TEMPORARY TABLE staging_users (
  id INT,
  nombre TEXT,
  email VARCHAR(320),
  hash_pw TEXT,
  rol TEXT,
  activo TEXT,
  creado_en TEXT,
  perm_ingresar TEXT
);
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_users
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, nombre, email, hash_pw, rol, activo, creado_en, perm_ingresar);

REPLACE INTO users (id, nombre, email, hash_pw, rol, activo, creado_en, perm_ingresar)
SELECT
  NULLIF(id,''),
  NULLIF(nombre,''),
  NULLIF(email,''),
  NULLIF(hash_pw,''),
  NULLIF(rol,''),
  CASE
    WHEN LOWER(TRIM(activo)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(activo)) IN ('f','false','0','n','no') THEN 0
    WHEN activo = '' THEN 1
    ELSE 0
  END,
  NULLIF(creado_en,''),
  CASE
    WHEN LOWER(TRIM(perm_ingresar)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(perm_ingresar)) IN ('f','false','0','n','no') THEN 0
    WHEN perm_ingresar = '' THEN 0
    ELSE 0
  END
FROM staging_users;
DROP TEMPORARY TABLE staging_users;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# Dispositivo: mapear booleans garantia_bool, etiq_garantia_ok, alquilado
load_devices_csv() {
  local table="devices"
  local file="$IN_DIR/$table.csv"
  if [[ ! -f "$file" ]]; then
    echo "WARN: no existe $file, se omite $table" >&2
    return 0
  fi
  echo "Importando (booleans mapeados) $file -> $table"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_devices;
CREATE TEMPORARY TABLE staging_devices (
  id INT,
  customer_id INT,
  marca_id INT,
  model_id INT,
  numero_serie TEXT,
  propietario TEXT,
  garantia_bool TEXT,
  etiq_garantia_ok TEXT,
  n_de_control TEXT,
  alquilado TEXT
);
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_devices
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado);

REPLACE INTO devices (id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado)
SELECT
  NULLIF(id,''),
  NULLIF(customer_id,''),
  NULLIF(marca_id,''),
  NULLIF(model_id,''),
  NULLIF(numero_serie,''),
  NULLIF(propietario,''),
  CASE
    WHEN LOWER(TRIM(garantia_bool)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(garantia_bool)) IN ('f','false','0','n','no') THEN 0
    WHEN garantia_bool = '' THEN NULL
    ELSE NULL
  END,
  CASE
    WHEN LOWER(TRIM(etiq_garantia_ok)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(etiq_garantia_ok)) IN ('f','false','0','n','no') THEN 0
    WHEN etiq_garantia_ok = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(n_de_control,''),
  CASE
    WHEN LOWER(TRIM(alquilado)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(alquilado)) IN ('f','false','0','n','no') THEN 0
    WHEN alquilado = '' THEN 0
    ELSE 0
  END
FROM staging_devices;
DROP TEMPORARY TABLE staging_devices;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# Handoffs: booleans firmado_cliente, firmado_empresa, remito_impreso
load_handoffs_csv() {
  local table="handoffs"
  local file="$IN_DIR/$table.csv"
  if [[ ! -f "$file" ]]; then
    echo "WARN: no existe $file, se omite $table" >&2
    return 0
  fi
  echo "Importando (booleans mapeados) $file -> $table"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_handoffs;
CREATE TEMPORARY TABLE staging_handoffs (
  id INT,
  ingreso_id INT,
  pdf_orden_salida TEXT,
  firmado_cliente TEXT,
  firmado_empresa TEXT,
  fecha TEXT,
  n_factura TEXT,
  factura_url TEXT,
  orden_taller TEXT,
  remito_impreso TEXT,
  fecha_impresion_remito TEXT,
  impresion_remito_url TEXT
);
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_handoffs
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, ingreso_id, pdf_orden_salida, firmado_cliente, firmado_empresa, fecha, n_factura, factura_url, orden_taller, remito_impreso, fecha_impresion_remito, impresion_remito_url);

REPLACE INTO handoffs (id, ingreso_id, pdf_orden_salida, firmado_cliente, firmado_empresa, fecha, n_factura, factura_url, orden_taller, remito_impreso, fecha_impresion_remito, impresion_remito_url)
SELECT
  NULLIF(id,''),
  NULLIF(ingreso_id,''),
  NULLIF(pdf_orden_salida,''),
  CASE
    WHEN LOWER(TRIM(firmado_cliente)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(firmado_cliente)) IN ('f','false','0','n','no') THEN 0
    WHEN firmado_cliente = '' THEN NULL
    ELSE NULL
  END,
  CASE
    WHEN LOWER(TRIM(firmado_empresa)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(firmado_empresa)) IN ('f','false','0','n','no') THEN 0
    WHEN firmado_empresa = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(fecha,''),
  NULLIF(n_factura,''),
  NULLIF(factura_url,''),
  NULLIF(orden_taller,''),
  CASE
    WHEN LOWER(TRIM(remito_impreso)) IN ('t','true','1','y','yes','si') THEN 1
    WHEN LOWER(TRIM(remito_impreso)) IN ('f','false','0','n','no') THEN 0
    WHEN remito_impreso = '' THEN NULL
    ELSE NULL
  END,
  NULLIF(fecha_impresion_remito,''),
  NULLIF(impresion_remito_url,'')
FROM staging_handoffs;
DROP TEMPORARY TABLE staging_handoffs;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Marcas (desde Access) ============
load_marcas_access_csv() {
  local file="$IN_DIR/marcas_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (upsert) $file -> marcas"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_marcas;
CREATE TEMPORARY TABLE staging_marcas ( nombre TEXT );
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_marcas
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES (nombre);
INSERT IGNORE INTO marcas(nombre)
SELECT DISTINCT NULLIF(TRIM(nombre),'') FROM staging_marcas WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_marcas;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Modelos (desde Access, con marca por nombre) ============
load_models_access_csv() {
  local file="$IN_DIR/models_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (upsert via join) $file -> models"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_models;
CREATE TEMPORARY TABLE staging_models ( marca_nombre TEXT, nombre TEXT );
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_models
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES (marca_nombre, nombre);
INSERT IGNORE INTO models(marca_id, nombre)
SELECT b.id, s.nombre
FROM staging_models s
JOIN marcas b ON b.nombre = s.marca_nombre
WHERE NULLIF(TRIM(s.nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_models;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Proveedores externos (desde Access) ============
load_proveedores_ext_access_csv() {
  local file="$IN_DIR/proveedores_externos_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (upsert) $file -> proveedores_externos"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_prov_ext;
CREATE TEMPORARY TABLE staging_prov_ext ( nombre TEXT, contacto TEXT );
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_prov_ext
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES (nombre, contacto);
INSERT IGNORE INTO proveedores_externos(nombre, contacto, telefono, email, direccion, notas)
SELECT NULLIF(TRIM(nombre),''), NULLIF(TRIM(contacto),'') , NULL, NULL, NULL, NULL
FROM staging_prov_ext WHERE NULLIF(TRIM(nombre),'') IS NOT NULL;
DROP TEMPORARY TABLE staging_prov_ext;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Devices (desde Access, con joins por nombre/codigo) ============
load_devices_access_csv2() {
  local file="$IN_DIR/devices_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (staging+merge) $file -> devices"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
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
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_devices_access
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, customer_cod_empresa, marca_nombre, modelo_nombre, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquiler);

REPLACE INTO devices (id, customer_id, marca_id, model_id, numero_serie, propietario, garantia_bool, etiq_garantia_ok, n_de_control, alquilado)
SELECT
  s.id,
  c.id,
  b.id,
  m.id,
  NULLIF(s.numero_serie,''),
  NULLIF(s.propietario,''),
  CASE
    WHEN LOWER(TRIM(s.garantia_bool)) IN ('t','true','-1','1','y','yes','si','sí') THEN 1
    WHEN LOWER(TRIM(s.garantia_bool)) IN ('f','false','0','n','no') THEN 0
    ELSE NULL
  END,
  CASE
    WHEN LOWER(TRIM(s.etiq_garantia_ok)) IN ('t','true','-1','1','y','yes','si','sí','ok','x') THEN 1
    WHEN LOWER(TRIM(s.etiq_garantia_ok)) IN ('f','false','0','n','no') THEN 0
    ELSE NULL
  END,
  NULLIF(s.n_de_control,''),
  CASE
    WHEN LOWER(TRIM(s.alquilado)) IN ('t','true','-1','1','y','yes','si','sí') THEN 1
    WHEN LOWER(TRIM(s.alquilado)) IN ('f','false','0','n','no') THEN 0
    ELSE 0
  END
FROM staging_devices_access s
LEFT JOIN customers c ON c.cod_empresa = s.customer_cod_empresa
LEFT JOIN marcas b ON b.nombre = s.marca_nombre
LEFT JOIN models m ON m.nombre = s.modelo_nombre AND m.marca_id = b.id;

DROP TEMPORARY TABLE staging_devices_access;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Ingresos (desde Access, 1:1 con Servicio) ============
load_ingresos_access_csv() {
  local file="$IN_DIR/ingresos_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (staging+merge) $file -> ingresos"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
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
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_ingresos_access
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado);

REPLACE INTO ingresos (id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, informe_preliminar, accesorios, remito_ingreso, comentarios, propietario_nombre, propietario_contacto, presupuesto_estado)
SELECT
  s.id,
  s.device_id,
  s.estado,
  s.motivo,
  STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s'),
  COALESCE(STR_TO_DATE(s.fecha_ingreso, '%Y-%m-%d %H:%i:%s'), NOW()),
  NULLIF(s.informe_preliminar,''),
  NULLIF(s.accesorios,''),
  NULLIF(s.remito_ingreso,''),
  NULLIF(s.comentarios,''),
  NULLIF(s.propietario_nombre,''),
  NULLIF(s.propietario_contacto,''),
  CASE
    WHEN s.presupuesto_estado IN ('pendiente','emitido','aprobado','rechazado','presupuestado') THEN s.presupuesto_estado
    ELSE 'pendiente'
  END
FROM staging_ingresos_access s;

DROP TEMPORARY TABLE staging_ingresos_access;
SET FOREIGN_KEY_CHECKS=1;
SQL
}

# ============ Derivados (desde Access) ============
load_equipos_derivados_access_csv() {
  local file="$IN_DIR/equipos_derivados_access.csv"
  if [[ ! -f "$file" ]]; then echo "WARN: no existe $file" >&2; return 0; fi
  echo "Importando (staging+merge) $file -> equipos_derivados"
  local filepath=$(cygpath -wa "$file" 2>/dev/null || realpath "$file")
  "${mysql_cli[@]}" --local-infile=1 <<SQL
SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_derivados;
CREATE TEMPORARY TABLE staging_derivados (
  ingreso_id INT,
  proveedor_nombre TEXT,
  remit_deriv TEXT,
  fecha_deriv TEXT,
  fecha_entrega TEXT
);
LOAD DATA LOCAL INFILE '${filepath//\\/\\\\}'
INTO TABLE staging_derivados
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(ingreso_id, proveedor_nombre, remit_deriv, fecha_deriv, fecha_entrega);

INSERT INTO equipos_derivados (ingreso_id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega)
SELECT s.ingreso_id, p.id, NULLIF(s.remit_deriv,''),
  NULLIF(NULLIF(s.fecha_deriv,''), '0000-00-00'),
  NULLIF(NULLIF(s.fecha_entrega,''), '0000-00-00')
FROM staging_derivados s
JOIN proveedores_externos p ON p.nombre = s.proveedor_nombre
ON DUPLICATE KEY UPDATE proveedor_id=VALUES(proveedor_id), remit_deriv=VALUES(remit_deriv), fecha_deriv=VALUES(fecha_deriv), fecha_entrega=VALUES(fecha_entrega);

DROP TEMPORARY TABLE staging_derivados;
SET FOREIGN_KEY_CHECKS=1;
SQL
}
tables=(
  customers
  marcas
  models
  locations
  devices
  ingresos
  quotes
  quote_items
  proveedores_externos
  equipos_derivados
  ingreso_events
  handoffs
  password_reset_tokens
  audit_log
)

echo "Importando CSV a MySQL desde $IN_DIR"
run_sql "SET NAMES utf8mb4"
run_sql "SET sql_log_bin=0"

# 1) Users con mapeo de booleanos (requerido para login)
load_users_csv

# 2) Tablas con booleans: devices y handoffs
load_devices_csv
load_handoffs_csv

# 3) Resto de tablas con import genérico
for t in "${tables[@]}"; do
  load_csv "$t"
done

run_sql "SET sql_log_bin=1"
echo "Importación completa"
