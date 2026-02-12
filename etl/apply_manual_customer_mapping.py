"""
Aplica un mapeo manual de cliente para ingresos con cliente 'MIGRACION'.

Input CSV esperado (UTF-8): outputs/migracion_manual_map.csv con columnas:
  os_id, razon_social

Para cada fila:
  - Asegura que exista el cliente en customers (crea si no existe)
  - Cambia el customer_id del device vinculado al ingreso OS dado

Uso:
  python etl/apply_manual_customer_mapping.py [--csv outputs/migracion_manual_map.csv]
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg  # type: ignore

DEFAULT_CSV = Path('outputs/migracion_manual_map.csv')


def connect_pg():
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def ensure_customer_id(cur, name: str) -> int:
    cur.execute("SELECT id FROM customers WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s)) LIMIT 1", (name,))
    r = cur.fetchone()
    if r:
        return int(r[0])
    cur.execute("INSERT INTO customers(razon_social) VALUES (%s) RETURNING id", (name,))
    return int(cur.fetchone()[0])


def main(argv):
    csv_path = DEFAULT_CSV
    if len(argv) > 1 and argv[1] == '--csv' and len(argv) > 2:
        csv_path = Path(argv[2])
    if not csv_path.exists():
        print(f"CSV no encontrado: {csv_path}")
        sys.exit(1)

    rows = []
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for r in cr:
            try:
                os_id = int((r.get('os_id') or '').strip())
            except Exception:
                continue
            name = (r.get('razon_social') or '').strip()
            if not name:
                continue
            rows.append((os_id, name))

    updated = 0
    with connect_pg() as cn:
        with cn.cursor() as cur:
            for os_id, rs in rows:
                cur.execute("SELECT device_id FROM ingresos WHERE id=%s", (os_id,))
                drow = cur.fetchone()
                if not drow:
                    continue
                dev_id = int(drow[0])
                cid = ensure_customer_id(cur, rs)
                cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (cid, dev_id))
                updated += 1
        cn.commit()
    print(f"Aplicado. Ingresos actualizados: {updated}")


if __name__ == '__main__':
    main(sys.argv)

