"""
Aplica un mapeo manual de tipo_equipo a la tabla models en PG.

Input: outputs/model_tipo_equipo_manual.csv con columnas:
  model_id,tipo_equipo

Actualiza sólo las filas indicadas. Útil para completar los pendientes listados en
outputs/models_missing_tipo_equipo.csv.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg  # type: ignore

CSV_PATH = Path('outputs/model_tipo_equipo_manual.csv')


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_pg():
    host = env('PG_HOST', env('POSTGRES_HOST', 'localhost'))
    port = int(env('PG_PORT', env('POSTGRES_PORT', '5433')))
    db = env('PG_DB', env('POSTGRES_DB', 'servicio_tecnico'))
    user = env('PG_USER', env('POSTGRES_USER', 'sepid'))
    pw = env('PG_PASSWORD', env('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def main():
    if not CSV_PATH.exists():
        print(f"CSV no encontrado: {CSV_PATH}")
        return
    rows = []
    with CSV_PATH.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for r in cr:
            try:
                mid = int((r.get('model_id') or '').strip())
            except Exception:
                continue
            te = (r.get('tipo_equipo') or '').strip()
            if not te:
                continue
            rows.append((mid, te))
    if not rows:
        print('No hay filas válidas en el CSV')
        return
    updated = 0
    with connect_pg() as cn:
        with cn.transaction():
            with cn.cursor() as cur:
                for mid, te in rows:
                    cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (te, mid))
                    if cur.rowcount:
                        updated += 1
        cn.commit()
    print('Aplicado tipo_equipo manual')
    print('Modelos actualizados:', updated)


if __name__ == '__main__':
    main()

