#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${1:-.env.prod}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "No existe $ENV_FILE" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${ENV_FILE}.rotated.${STAMP}"
cp "$ENV_FILE" "$OUT_FILE"

generate_secret() {
  python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
}

DJANGO_SECRET_KEY="$(generate_secret)"
JWT_SECRET="$(generate_secret)"
POSTGRES_PASSWORD="$(generate_secret)"

python - "$OUT_FILE" "$DJANGO_SECRET_KEY" "$JWT_SECRET" "$POSTGRES_PASSWORD" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
values = {
    "DJANGO_SECRET_KEY": sys.argv[2],
    "JWT_SECRET": sys.argv[3],
    "POSTGRES_PASSWORD": sys.argv[4],
}

lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key, _, _ = line.partition("=")
    key = key.strip()
    if key in values:
        out.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in values.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

echo "Archivo generado: $OUT_FILE"
echo ""
echo "Se rotaron claves internas:"
echo "- DJANGO_SECRET_KEY"
echo "- JWT_SECRET"
echo "- POSTGRES_PASSWORD"
echo ""
echo "Pendiente manual (externo):"
echo "- TIENDANUBE_ACCESS_TOKEN / TIENDANUBE_WEBHOOK_SECRET"
echo "- credenciales/certificados ARCA"
echo ""
echo "Siguiente paso sugerido:"
echo "1) Revisar $OUT_FILE"
echo "2) Reemplazar .env.prod con ese contenido"
echo "3) Reiniciar stack: docker compose -f docker-compose.prod.yml up -d --build"
