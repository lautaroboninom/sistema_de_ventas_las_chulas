#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detecta nombres de modelos potencialmente duplicados o mal escritos
comparando contra listas oficiales por marca (scripts/official_models_data.py)
y usando coincidencia difusa intra-marca.

Salida: listado por consola y CSV con sugerencias.

Uso:
  POSTGRES_* por env; salida CSV en scripts/output/model_official_suggestions.csv
  python scripts/find_model_typos_vs_official.py
  python scripts/find_model_typos_vs_official.py --brand 'Philips Respironics'
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg  # type: ignore

from scripts.official_models_data import OFFICIAL_MODELS


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


_sep_re = re.compile(r"[\s\-_/.,]+")


def norm(s: str) -> str:
    s = (s or "").strip().upper()
    s = _sep_re.sub("", s)
    return s


@dataclass
class Suggestion:
    brand: str
    model_db: str
    model_official: Optional[str]
    similarity: float
    reason: str


def best_match(name: str, candidates: List[str]) -> Tuple[Optional[str], float]:
    best = None
    best_score = 0.0
    for c in candidates:
        score = SequenceMatcher(None, norm(name), norm(c)).ratio()
        if score > best_score:
            best, best_score = c, score
    return best, best_score


def find_typos(cur, brand: str, threshold: float = 0.86) -> List[Suggestion]:
    cur.execute("SELECT DISTINCT m.nombre FROM models m JOIN marcas b ON b.id=m.marca_id WHERE b.nombre=%s", (brand,))
    db_models = sorted([str(r[0]) for r in cur.fetchall()])
    official = OFFICIAL_MODELS.get(brand, {}).get('models', [])

    suggestions: List[Suggestion] = []
    onorms = {norm(x): x for x in official}

    # 1) Coincidencias exactas por normalización
    for m in db_models:
        nm = norm(m)
        if nm in onorms:
            continue  # OK
        if not official:
            # Sin lista oficial: sólo duplicados intra-marca por separadores
            for other in db_models:
                if other == m:
                    continue
                if norm(other) == nm:
                    suggestions.append(Suggestion(brand, m, other, 1.0, 'normalize-equal'))
                    break
            continue
        # 2) Buscar mejor match oficial
        off, score = best_match(m, official)
        if off and score >= threshold:
            suggestions.append(Suggestion(brand, m, off, score, 'official-similar'))
        else:
            # 3) Si no hay match oficial fuerte, ver duplicado intra-marca
            for other in db_models:
                if other == m:
                    continue
                if norm(other) == nm:
                    suggestions.append(Suggestion(brand, m, other, 1.0, 'normalize-equal'))
                    break
    return suggestions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--brand', help='Filtrar por marca exacta')
    ap.add_argument('--threshold', type=float, default=0.86)
    args = ap.parse_args()

    outdir = Path('scripts/output')
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / 'model_official_suggestions.csv'

    cn = connect_pg()
    with cn.cursor() as cur, outfile.open('w', newline='', encoding='utf-8') as f:
        cw = csv.writer(f)
        cw.writerow(['brand','model_db','suggested_official','similarity','reason'])

        brands = []
        if args.brand:
            brands = [args.brand]
        else:
            cur.execute("SELECT DISTINCT nombre FROM marcas ORDER BY nombre")
            brands = [str(r[0]) for r in cur.fetchall()]

        total = 0
        for b in brands:
            suggs = find_typos(cur, b, threshold=args.threshold)
            if not suggs:
                continue
            print(f"Marca: {b}")
            for s in suggs:
                print(f"  - DB: {s.model_db} -> Oficial: {s.model_official or '(intra-brand dup)'} ({s.similarity:.2f}) [{s.reason}]")
                cw.writerow([s.brand, s.model_db, s.model_official or '', f"{s.similarity:.3f}", s.reason])
                total += 1
            print()
        print(f"Total sugerencias: {total}")


if __name__ == '__main__':
    main()

