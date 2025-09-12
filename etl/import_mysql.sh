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

tables=(
  users
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

for t in "${tables[@]}"; do
  load_csv "$t"
done

run_sql "SET sql_log_bin=1"
echo "Importación completa"
