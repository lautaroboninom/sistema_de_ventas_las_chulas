#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Consolidar variantes dentro de un modelo base por marca, preservando variantes
en catálogo (marca_tipos_equipo/marca_series/marca_series_variantes) y sin
perder asociaciones de dispositivos.

Estrategia cauta, con reglas por marca:
- BMC: agrupa sufijos como T-25T / Y-25T / 25T / 25S / B25T / C20 / H-80x bajo
  bases BPAP G2 / CPAP G1 / RESmart G1/G2/G2S según corresponda.
- ResMed: S9 (Auto/Elite/AutoSet) como variantes de S9.

Por defecto corre en DRY-RUN y escribe un CSV con el plan.

Uso:
  POSTGRES_* por env
  python scripts/consolidate_variants.py                 # dry-run
  python scripts/consolidate_variants.py --apply         # aplica cambios
  python scripts/consolidate_variants.py --brand BMC     # filtrar marca
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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


@dataclass
class ModelRow:
    id: int
    brand: str
    name: str
    tipo: str
    variante: str


def load_models_by_brand(cur, brand: str) -> List[ModelRow]:
    cur.execute(
        """
        SELECT m.id, b.nombre, m.nombre, COALESCE(TRIM(m.tipo_equipo),''), COALESCE(TRIM(m.variante),'')
        FROM models m JOIN marcas b ON b.id=m.marca_id
        WHERE b.nombre=%s
        ORDER BY m.nombre
        """,
        (brand,),
    )
    return [ModelRow(int(r[0]), str(r[1]), str(r[2] or ''), str(r[3] or ''), str(r[4] or '')) for r in cur.fetchall()]


def ensure_catalog_for_series(cur, marca_id: int, tipo_txt: str, serie_nombre: str) -> Tuple[Optional[int], Optional[int]]:
    if not tipo_txt or not serie_nombre:
        return None, None
    cur.execute(
        "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_txt),
    )
    r = cur.fetchone()
    if not r:
        try:
            cur.execute(
                "INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE)",
                (marca_id, tipo_txt),
            )
        except Exception:
            pass
        cur.execute(
            "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            (marca_id, tipo_txt),
        )
        r = cur.fetchone()
    tipo_id = int(r[0]) if r else None
    if not tipo_id:
        return None, None
    cur.execute(
        "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_id, serie_nombre),
    )
    r2 = cur.fetchone()
    if not r2:
        cur.execute(
            "INSERT INTO marca_series(marca_id, tipo_id, nombre, activo) VALUES (%s,%s,%s,TRUE)",
            (marca_id, tipo_id, serie_nombre),
        )
        cur.execute(
            "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            (marca_id, tipo_id, serie_nombre),
        )
        r2 = cur.fetchone()
    serie_id = int(r2[0]) if r2 else None
    return tipo_id, serie_id


def add_variant_to_catalog(cur, marca_id: int, tipo_id: int, serie_id: int, variant: str):
    v = (variant or '').strip()
    if not v:
        return
    cur.execute(
        "SELECT 1 FROM marca_series_variantes WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_id, serie_id, v),
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo) VALUES (%s,%s,%s,%s,TRUE)",
            (marca_id, tipo_id, serie_id, v),
        )


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


# ===== Rules per brand =====

_sep_re = re.compile(r"\s*[-\s]\s*")


def _clean_variant(v: str) -> str:
    v = v.strip().upper()
    v = v.replace(' ', '')
    v = v.replace('_', '')
    v = v.replace('--', '-')
    v = v.replace('T25T', 'T-25T') if 'T25T' in v and 'T-25T' not in v else v
    v = v.replace('Y25T', 'Y-25T') if 'Y25T' in v and 'Y-25T' not in v else v
    v = v.replace('B25T', 'B-25T') if 'B25T' in v and 'B-25T' not in v else v
    return v


def parse_bmc_base_variant(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    n = re.sub(r"\s+", " ", n)
    # Known prefixes
    m = re.match(r"^(RESMART)\s+(GII|G2|G1|G3|G2S)\s*(.*)$", n)
    if m:
        base = f"RESmart {m.group(2)}".replace('GII', 'GII').replace('  ', ' ')
        var = _clean_variant(m.group(3))
        return base, var
    m = re.match(r"^(BPAP|CPAP)\s+(G2S|G3|G2|G1)\s*(.*)$", n)
    if m:
        base = f"{m.group(1)} {m.group(2)}"
        var = _clean_variant(m.group(3))
        return base, var
    m = re.match(r"^(G2S|G3|G2|G1)\s+(.*)$", n)
    if m:
        base = m.group(1)
        var = _clean_variant(m.group(2))
        return base, var
    # H-80x forms
    m = re.match(r"^(H)[ -]?(80[AM])$", n)
    if m:
        return "H-80", m.group(2)
    return None


def parse_resmed_base_variant(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^(S9)\s*(.*)$", n)
    if m:
        base = 'S9'
        var = m.group(2).strip()
        return base, var
    return None


def parse_pr_base_variant(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^(REMSTAR)\s*(.*)$", n)
    if m:
        base = 'REMstar'
        var = m.group(2).strip()
        return base, var
    m = re.match(r"^(SYSTEM\s+ONE)\s*(.*)$", n)
    if m:
        base = 'System One'
        var = m.group(2).strip()
        return base, var
    m = re.match(r"^(C[-\s]?SERIES)\s*(.*)$", n)
    if m:
        base = 'C-Series'
        var = m.group(2).strip().strip('()')
        return base, var
    return None


def parse_breas_isleep(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^(ISLEEP)\s*(.*)$", n)
    if m:
        base = 'iSleep'
        var = m.group(2).strip().replace('  ', ' ')
        return base, var
    # casos comunes escritos como SLEEP 20 I (corresponde a iSleep 20i)
    m = re.match(r"^SLEEP\s*([0-9]{2})(?:\s*I)?$", n)
    if m:
        return 'iSleep', f"{m.group(1)}I"
    m = re.match(r"^GE?ISLEEP\s*(.*)$", n)
    if m:
        return 'iSleep', m.group(1).strip()
    return None


def parse_longfian_jay(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^JAY[-\s]?([0-9]{1,3}[A-Z]?)$", n)
    if m:
        return 'JAY', m.group(1)
    return None


def parse_dev_vacuaide(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^VACUAIDE[\s-]*(.*)$", n)
    if m:
        return 'VacuAide', m.group(1).strip()
    return None


def parse_covidien_kangaroo(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^KANGAROO[\s-]*(.*)$", n)
    if m:
        v = m.group(1).strip()
        v = 'ePump' if v.replace(' ', '').upper() in {'EPUMP','E-PUMP'} else v
        return 'Kangaroo', v
    return None


def parse_kangaroo_brand(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    if not n.startswith('KANGAROO'):
        return None
    v = n[len('KANGAROO'):].strip()
    v = v.replace('E-PUMP', 'ePump')
    v = 'ePump' if v.replace(' ', '').upper() in {'EPUMP','E-PUMP'} else v.title()
    return 'Kangaroo', v


def parse_konsung_series(name: str) -> Optional[Tuple[str, str]]:
    n = (name or '').strip().upper()
    m = re.match(r"^(9E)[-\s]?(.+)$", n)
    if m:
        return '9E', m.group(2).strip()
    return None


BRAND_RULES = {
    'BMC': parse_bmc_base_variant,
    'ResMed': parse_resmed_base_variant,
    'Philips Respironics': parse_pr_base_variant,
    'Breas Medical': parse_breas_isleep,
    'Longfian': parse_longfian_jay,
    'Drive DeVilbiss Healthcare': parse_dev_vacuaide,
    'Covidien': parse_covidien_kangaroo,
    'Kangaroo': parse_kangaroo_brand,
    'Konsung': parse_konsung_series,
}


def consolidate_brand(cur, brand: str, *, logs: List[str], rows_out: List[List[str]]):
    parser = BRAND_RULES.get(brand)
    if not parser:
        return
    models = load_models_by_brand(cur, brand)
    if not models:
        return
    bid = brand_id(cur, brand)
    if not bid:
        return
    # Group
    groups: Dict[str, List[ModelRow]] = {}
    parsed: Dict[int, Tuple[str, str]] = {}
    for r in models:
        pv = parser(r.name)
        if not pv:
            continue
        base, var = pv
        base = base.strip()
        var = var.strip(' .')
        if not base:
            continue
        parsed[r.id] = (base, var)
        groups.setdefault(base, []).append(r)

    BRAND_DEFAULT_TIPO = {
        'Philips Respironics': 'CPAP/BPAP',
        'BMC': 'CPAP/BPAP',
        'Breas Medical': 'CPAP',
        'Longfian': 'CONCENTRADOR DE OXIGENO',
        'Covidien': 'BOMBA DE ALIMENTACION',
        'Drive DeVilbiss Healthcare': None,
        'ResMed': 'CPAP/BPAP',
    }

    for base, items in groups.items():
        # choose canonical: prefer exact base name match; else lowest id
        canon = None
        for r in items:
            if r.name.strip().upper() == base.upper():
                canon = r
                break
        if not canon:
            canon = sorted(items, key=lambda x: x.id)[0]
        tipo_eff = (canon.tipo or '').strip() or (items[0].tipo or '').strip() or (BRAND_DEFAULT_TIPO.get(brand) or '')
        # ensure catalog (solo si hay tipo)
        tipo_id, serie_id = (None, None)
        if tipo_eff:
            tipo_id, serie_id = ensure_catalog_for_series(cur, bid, (tipo_eff or ''), base)
        # rename canonical to base if needed
        if canon.name != base:
            cur.execute("UPDATE models SET nombre=%s WHERE id=%s", (base, canon.id))
            logs.append(f"rename: {brand} '{canon.name}' -> '{base}' (id={canon.id})")
        # set tipo_equipo en el canónico si faltaba
        if tipo_eff and not (canon.tipo or '').strip():
            cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo_eff, canon.id))
        # variants: from all items parsed
        for r in items:
            b, v = parsed.get(r.id, (base, ''))
            v = v.strip()
            if r.id == canon.id:
                if v and tipo_id and serie_id:
                    add_variant_to_catalog(cur, bid, tipo_id, serie_id, v)
                continue
            # move devices to canon
            cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (canon.id, r.id))
            # collect variant
            if v and tipo_id and serie_id:
                add_variant_to_catalog(cur, bid, tipo_id, serie_id, v)
            # delete alias model
            cur.execute("DELETE FROM models WHERE id=%s", (r.id,))
            logs.append(f"merge: {brand} '{r.name}' -> '{base}' (canon_id={canon.id}, var='{v}')")
            rows_out.append([brand, str(r.id), r.name, base, v])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Aplica cambios (default dry-run)')
    ap.add_argument('--brand', help='Filtrar por marca exacta (case sensitive)')
    args = ap.parse_args()

    outdir = Path('scripts/output')
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / 'consolidate_variants_plan.csv'

    logs: List[str] = []
    rows_out: List[List[str]] = []
    cn = connect_pg()
    try:
        if args.apply:
            cn.autocommit = False
        with cn.cursor() as cur:
            brands = [args.brand] if args.brand else list(BRAND_RULES.keys())
            for b in brands:
                consolidate_brand(cur, b, logs=logs, rows_out=rows_out)
            if args.apply:
                cn.commit()
            else:
                cn.rollback()
    finally:
        try:
            cn.close()
        except Exception:
            pass

    with outfile.open('w', newline='', encoding='utf-8') as f:
        cw = csv.writer(f)
        cw.writerow(['brand','model_id','from_model','to_base_model','variant'])
        for row in rows_out:
            cw.writerow(row)

    print(f"=== Consolidate Variants ({'APPLY' if args.apply else 'DRY-RUN'}) ===")
    for l in logs:
        print(' *', l)
    print(f"Plan guardado: {outfile}")


if __name__ == '__main__':
    main()
