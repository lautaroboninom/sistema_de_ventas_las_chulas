#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lista modelos obvios duplicados por marca usando normalización simple
del nombre de modelo (mayúsculas y quitando separadores: espacios, guiones,
slashes y puntos).

Uso:
  POSTGRES_* por env (POSTGRES_HOST/PORT/DB/USER/PASSWORD)
  python scripts/list_model_duplicates.py            # todas las marcas
  python scripts/list_model_duplicates.py --brand Philips Respironics  # filtrar
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple

import psycopg  # type: ignore


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


_sep_re = re.compile(r"[\s\-_/.,]+")


def norm_model(name: str) -> str:
    if name is None:
        return ""
    s = name.strip().upper()
    # Normalizar separadores comunes
    s = _sep_re.sub("", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", help="Filtrar por marca exacta (case sensitive)")
    args = ap.parse_args()

    cn = connect_pg()
    with cn.cursor() as cur:
        if args.brand:
            cur.execute(
                """
                SELECT b.nombre AS brand, m.nombre AS model
                FROM models m JOIN marcas b ON b.id=m.marca_id
                WHERE b.nombre=%s
                ORDER BY b.nombre, m.nombre
                """,
                (args.brand,),
            )
        else:
            cur.execute(
                """
                SELECT b.nombre AS brand, m.nombre AS model
                FROM models m JOIN marcas b ON b.id=m.marca_id
                ORDER BY b.nombre, m.nombre
                """
            )
        rows = cur.fetchall()

    by_brand: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for brand, model in rows:
        b = str(brand)
        m = str(model or "")
        key = norm_model(m)
        if m not in by_brand[b][key]:
            by_brand[b][key].append(m)

    total_groups = 0
    for brand in sorted(by_brand.keys()):
        groups = [(k, v) for (k, v) in by_brand[brand].items() if len(v) > 1]
        if not groups:
            continue
        print(f"Marca: {brand}")
        for _, models in sorted(groups, key=lambda t: (t[0])):
            print("  - " + " | ".join(models))
            total_groups += 1
        print()

    if total_groups == 0:
        print("No se detectaron duplicados obvios por normalización de separadores.")


if __name__ == "__main__":
    main()

