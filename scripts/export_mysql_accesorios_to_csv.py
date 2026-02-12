"""
Exporta la tabla de accesorios desde MySQL a un CSV.

Lee credenciales desde argumentos o variables de entorno:
  MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE (o MYSQL_DB)

Uso rápido (si MySQL de 'Nuevo Sistema' está publicado en 3306):
  python scripts/export_mysql_accesorios_to_csv.py \
    --host 127.0.0.1 --port 3306 --user sepid --password supersegura \
    --db servicio_tecnico --out etl/out/catalogo_accesorios_mysql.csv
"""

from __future__ import annotations

import csv
import os
import sys
import argparse
from typing import List

import pymysql  # type: ignore


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_mysql(host: str, port: int, user: str, password: str, db: str):
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def table_exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (table,))
        return cur.fetchone() is not None


def fetch_columns(conn, table: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(f"DESCRIBE `{table}`")
        return [row["Field"] for row in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Exporta catalogo_accesorios desde MySQL a CSV")
    ap.add_argument("--host", default=env("MYSQL_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(env("MYSQL_PORT", "3306") or 3306))
    ap.add_argument("--user", default=env("MYSQL_USER", "root"))
    ap.add_argument("--password", default=env("MYSQL_PASSWORD", ""))
    ap.add_argument("--db", default=env("MYSQL_DATABASE", env("MYSQL_DB", "servicio_tecnico")))
    ap.add_argument("--table", default="catalogo_accesorios")
    ap.add_argument("--out", default=os.path.join("etl", "out", "catalogo_accesorios_mysql.csv"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    conn = connect_mysql(args.host, args.port, args.user, args.password, args.db)
    try:
        if not table_exists(conn, args.table):
            print(f"Tabla '{args.table}' no existe en MySQL (db={args.db}).", file=sys.stderr)
            print("No se exportó nada. Verificá que el catálogo exista.", file=sys.stderr)
            return 2

        cols = fetch_columns(conn, args.table)
        # Orden amigable si existen estas columnas
        preferred = [c for c in ("id", "nombre", "activo") if c in cols]
        rest = [c for c in cols if c not in preferred]
        sel_cols = preferred + rest

        sql = f"SELECT {', '.join('`'+c+'`' for c in sel_cols)} FROM `{args.table}` ORDER BY `{sel_cols[0]}`"
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=sel_cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in sel_cols})

        print(f"Exportado {len(rows)} filas a {args.out}")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

