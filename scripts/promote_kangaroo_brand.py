#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Promueve modelos 'Kangaroo*' que estén bajo la marca 'Covidien' a la marca
'Kangaroo', preservando dispositivos y variantes. Si el nombre del modelo en
Covidien es 'Kangaroo ePump', se mueve a marca Kangaroo y se consolida luego
como base 'Kangaroo' con variante 'ePump' (usar consolidate_variants.py).

Uso:
  POSTGRES_* por env
  python scripts/promote_kangaroo_brand.py            # dry-run
  python scripts/promote_kangaroo_brand.py --apply    # aplica cambios
"""

from __future__ import annotations

import argparse
import os
from typing import Optional, Tuple

import psycopg  # type: ignore


def env(name: str, default: Optional[str] = None) -> Optional[str]:
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


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_brand(cur, name: str) -> int:
    bid = brand_id(cur, name)
    if bid is not None:
        return bid
    cur.execute("INSERT INTO marcas(nombre) VALUES (%s) RETURNING id", (name,))
    return int(cur.fetchone()[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Aplica cambios (default dry-run)')
    args = ap.parse_args()

    logs = []
    cn = connect_pg()
    try:
        if args.apply:
            cn.autocommit = False
        with cn.cursor() as cur:
            bid_covidien = brand_id(cur, 'Covidien')
            if not bid_covidien:
                print('No existe marca Covidien; nada para promover')
                return
            bid_kangaroo = ensure_brand(cur, 'Kangaroo')
            cur.execute(
                """
                SELECT id, nombre FROM models
                WHERE marca_id=%s AND UPPER(nombre) LIKE 'KANGAROO%%'
                ORDER BY nombre
                """,
                (bid_covidien,),
            )
            rows = cur.fetchall() or []
            for mid, name in rows:
                # Si existe homónimo en Kangaroo, mergear
                cur.execute(
                    "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    (bid_kangaroo, name),
                )
                r = cur.fetchone()
                if r:
                    dst_id = int(r[0])
                    cur.execute("UPDATE devices SET model_id=%s, marca_id=%s WHERE model_id=%s", (dst_id, bid_kangaroo, mid))
                    cur.execute("DELETE FROM models WHERE id=%s", (mid,))
                    logs.append(f"merge: Covidien '{name}' -> Kangaroo (id={dst_id})")
                else:
                    # Mover modelo entero a marca Kangaroo
                    cur.execute("UPDATE models SET marca_id=%s WHERE id=%s", (bid_kangaroo, mid))
                    cur.execute("UPDATE devices SET marca_id=%s WHERE model_id=%s", (bid_kangaroo, mid))
                    logs.append(f"move: Covidien '{name}' -> Kangaroo")
            if args.apply:
                cn.commit()
            else:
                cn.rollback()
    finally:
        try:
            cn.close()
        except Exception:
            pass

    print(f"=== Promote Kangaroo ({'APPLY' if args.apply else 'DRY-RUN'}) ===")
    for l in logs:
        print(' *', l)


if __name__ == '__main__':
    main()

