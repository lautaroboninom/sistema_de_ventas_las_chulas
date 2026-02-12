"""
Reemplaza el catálogo de accesorios en PostgreSQL por el listado del CSV
generado desde MySQL (etl/out/catalogo_accesorios_mysql.csv).

ATENCIÓN: elimina TODAS las filas de ingreso_accesorios para poder
recrear el catálogo (FK con ON DELETE RESTRICT). Ejecuta todo en una
transacción.

Lee conexión de entorno: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
POSTGRES_USER, POSTGRES_PASSWORD.

Uso:
  python scripts/replace_pg_accesorios_from_csv.py \
    --csv etl/out/catalogo_accesorios_mysql.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import List, Tuple

import psycopg


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def read_csv_rows(path: str) -> List[Tuple[int, str, bool]]:
    rows: List[Tuple[int, str, bool]] = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rid = int((row.get("id") or "").strip())
            except Exception:
                continue
            nombre = (row.get("nombre") or "").strip()
            activo_raw = (row.get("activo") or "1").strip()
            activo = str(activo_raw) in ("1", "true", "True")
            if not nombre:
                continue
            rows.append((rid, nombre, activo))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join("etl", "out", "catalogo_accesorios_mysql.csv"))
    args = ap.parse_args()

    data = read_csv_rows(args.csv)
    if not data:
        print("CSV vacío o no válido:", args.csv)
        return 2

    conn = connect_pg()
    with conn:
        with conn.cursor() as cur:
            # Eliminar vínculos primero (FK a catalogo_accesorios)
            cur.execute("DELETE FROM ingreso_accesorios")
            # Limpiar catálogo
            cur.execute("DELETE FROM catalogo_accesorios")
            # Insertar con IDs explícitos
            cur.executemany(
                """
                INSERT INTO catalogo_accesorios(id, nombre, activo)
                OVERRIDING SYSTEM VALUE
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                data,
            )
            # Ajustar secuencia
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('catalogo_accesorios','id'), (SELECT COALESCE(MAX(id),0) FROM catalogo_accesorios), true)"
            )
            # Reporte
            cur.execute("SELECT COUNT(*) FROM catalogo_accesorios")
            n = cur.fetchone()[0]
            print(f"catalogo_accesorios cargado: {n} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

