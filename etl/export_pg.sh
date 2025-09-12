#!/usr/bin/env bash
set -euo pipefail

# Exporta datos desde Postgres a CSV (UTF-8) en orden topológico
# Requiere psql en el entorno donde se ejecute (usar contenedor de Postgres si es necesario).

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=sepid}"
: "${PGDATABASE:=servicio_tecnico}"

OUT_DIR=${OUT_DIR:-"etl/out"}
mkdir -p "$OUT_DIR"

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

echo "Exportando CSV desde PG -> $OUT_DIR"
for t in "${tables[@]}"; do
  f="$OUT_DIR/$t.csv"
  echo "- $t -> $f"
  psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" \
    -c "\\COPY public.$t TO STDOUT WITH (FORMAT CSV, HEADER, FORCE_QUOTE *)" > "$f"
done

echo "Listo. Archivos en $OUT_DIR" 

