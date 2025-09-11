#!/usr/bin/env bash
set -euo pipefail

FILE=${1:-db/admin_scripts.sql}
CONTAINER=${2:-sepid-db}
USER=${POSTGRES_USER:-sepid}
DB=${POSTGRES_DB:-servicio_tecnico}

if [[ ! -f "$FILE" ]]; then
  echo "No se encontró el archivo '$FILE'" >&2
  exit 1
fi

echo "Ejecutando SQL en contenedor '$CONTAINER' contra DB '$DB'..."
docker exec -i "$CONTAINER" psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 -q < "$FILE"
echo "OK"

