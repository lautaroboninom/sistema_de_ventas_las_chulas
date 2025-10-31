#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Corrige devices LONGFIAN con modelo 'JAY' sin sufijo usando prefijos del número de serie.

Regla confirmada:
- Serial que inicia con 'MZJ10S' => modelo 'JAY-10'.

Modo por defecto: dry-run (solo plan). Con --apply aplica cambios.
Salida plan: scripts/output/longfian_from_serial_prefix_plan.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg  # type: ignore


OUT_DIR = Path("scripts/output")
OUT_CSV = OUT_DIR / "longfian_from_serial_prefix_plan.csv"


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


def norm_ns(s: Optional[str]) -> str:
    if not s:
        return ""
    t = (s or "").strip().upper()
    t = t.replace(" ", "").replace("-", "")
    return t


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_model(cur, marca_id: int, nombre: str) -> int:
    cur.execute(
        "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
        (marca_id, nombre),
    )
    r = cur.fetchone()
    if r:
        return int(r[0])
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (marca_id, nombre))
    return int(cur.fetchone()[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica cambios (por defecto: dry-run)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cn = connect_pg()
    if args.apply:
        cn.autocommit = False
    try:
        with cn.cursor() as cur:
            bid = brand_id(cur, "Longfian") or brand_id(cur, "LONGFIAN")
            if not bid:
                raise SystemExit("Marca 'Longfian' no encontrada en SR")
            # Devices LONGFIAN cuyo modelo es 'JAY' (sin sufijo)
            cur.execute(
                """
                SELECT d.id, d.model_id, COALESCE(TRIM(d.numero_serie), '') AS ns
                FROM devices d
                JOIN models m ON m.id=d.model_id
                WHERE d.marca_id=%s AND UPPER(TRIM(m.nombre))='JAY'
                """,
                (bid,),
            )
            rows = cur.fetchall() or []

            # Reglas: prefijo de serie -> modelo canónico
            rules = [
                ('MZJ10S', 'JAY-10'),
                ('MZJ2P',  'JAY-10D'),
            ]

            # Asegurar modelos destino bajo Longfian
            ensured: Dict[str, int] = {}
            for _, model in rules:
                if model not in ensured:
                    ensured[model] = ensure_model(cur, bid, model)

            planned: List[List[str]] = []
            updated = 0

            for did, mid, ns in rows:
                t = norm_ns(ns)
                target: Optional[str] = None
                for prefix, model in rules:
                    if t.startswith(prefix):
                        target = model
                        break
                if not target:
                    continue
                planned.append([str(int(did)), str(ns), 'JAY', target])
                if args.apply:
                    cur.execute("UPDATE devices SET model_id=%s WHERE id=%s", (ensured[target], int(did)))
                    updated += 1

            # Guardar plan
            with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
                cw = csv.writer(f)
                cw.writerow(['device_id','numero_serie','modelo_actual','modelo_nuevo'])
                for r in planned:
                    cw.writerow(r)

            if args.apply:
                cn.commit()

            print("=== Fix LONGFIAN JAY por prefijo ===")
            print(f"Plan: {OUT_CSV}")
            print(f"Reglas: MZJ10S->JAY-10, MZJ2P->JAY-10D")
            print(f"Devices con cambio por reglas: {len(planned)}")
            if args.apply:
                print(f"Actualizados: {updated}")
            else:
                print("Modo: DRY-RUN (sin cambios)")
    finally:
        try:
            cn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
