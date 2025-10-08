"""
Completa models.tipo_equipo en Postgres usando:
- Mapeo desde CSV de Access: etl/out/model_tipo_equipo_access.csv
- Heurísticas provistas:
  * Marca 'E&M' => 'CARDIODESFIBRILADOR'
  * Marca 'Meditech' => 'MONITOR MULTIPARAMETRICO' excepto modelos tipo 'Central' => 'CENTRAL DE MONITOREO'
  * Marca 'LONGFIAN' => 'CONCENTRADOR DE OXIGENO' excepto modelo 'JAY-10D' => 'CONCENTRADOR DE OXIGENO PORTATIL'

Solo actualiza donde tipo_equipo está NULL o vacío.

Salida: outputs/model_tipo_equipo_backfill.csv
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import psycopg  # type: ignore

ACCESS_MAP = Path('etl/out/model_tipo_equipo_access.csv')


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


def norm(s: Optional[str]) -> str:
    if not s:
        return ''
    s2 = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s2 = s2.lower().strip()
    s2 = re.sub(r"\s+", " ", s2)
    return s2


def alnum_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(s))


def load_access_map() -> Dict[Tuple[str, str], str]:
    m: Dict[Tuple[str, str], str] = {}
    if not ACCESS_MAP.exists():
        return m
    with ACCESS_MAP.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for r in cr:
            mb = norm(r.get('marca_nombre'))
            mm = norm(r.get('modelo_nombre'))
            te = (r.get('tipo_equipo') or '').strip()
            if mb and mm and te:
                m[(mb, mm)] = te
    return m


def heuristic_tipo_equipo(marca: str, modelo: str) -> Optional[str]:
    mb = norm(marca)
    mm = norm(modelo)
    mm_key = alnum_key(modelo)
    # E&M => CARDIODESFIBRILADOR
    if alnum_key(mb) in ("em", "eym"):
        return "CARDIODESFIBRILADOR"
    # Meditech => MONITOR MULTIPARAMETRICO, excepto Central
    if mb == 'meditech':
        if 'central' in mm:
            return 'CENTRAL DE MONITOREO'
        return 'MONITOR MULTIPARAMETRICO'
    # LONGFIAN => CONCENTRADOR, excepto JAY-10D
    if mb == 'longfian':
        if mm_key == 'jay10d' or 'jay10d' in mm_key:
            return 'CONCENTRADOR DE OXIGENO PORTATIL'
        return 'CONCENTRADOR DE OXIGENO'
    return None


def main():
    out_csv = Path('outputs/model_tipo_equipo_backfill.csv')
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    access_map = load_access_map()

    updated_access = 0
    updated_heur = 0
    skipped = 0
    total = 0
    rows_out: List[Tuple[int, str, str, str, str]] = []
    unresolved_rows: List[Tuple[int, str, str]] = []

    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, COALESCE(b.nombre,''), COALESCE(m.nombre,''), COALESCE(m.tipo_equipo,'')
                FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
                WHERE m.tipo_equipo IS NULL OR LENGTH(TRIM(m.tipo_equipo))=0
                """
            )
            models = cur.fetchall()
        if not models:
            print('No hay modelos pendientes de tipo_equipo')
            return
        with cn.transaction():
            with cn.cursor() as cur:
                for (mid, marca_nom, modelo_nom, tipo_e) in models:
                    total += 1
                    mb = norm(marca_nom)
                    mm = norm(modelo_nom)
                    set_to: Optional[str] = None
                    source = ''
                    # 1) Access map exacto
                    if (mb, mm) in access_map:
                        set_to = access_map[(mb, mm)]
                        source = 'access_csv'
                    else:
                        # 2) Heurística
                        te = heuristic_tipo_equipo(marca_nom, modelo_nom)
                        if te:
                            set_to = te
                            source = 'heuristic'
                    if set_to:
                        cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (set_to, mid))
                        if source == 'access_csv':
                            updated_access += 1
                        else:
                            updated_heur += 1
                        rows_out.append((int(mid), str(marca_nom), str(modelo_nom), set_to, source))
                    else:
                        skipped += 1
                        unresolved_rows.append((int(mid), str(marca_nom), str(modelo_nom)))
        cn.commit()

    with out_csv.open('w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['model_id','marca','modelo','tipo_equipo','source'])
        for r in rows_out:
            cw.writerow(r)

    # export unresolved for revisión manual
    pend_csv = Path('outputs/models_missing_tipo_equipo.csv')
    with pend_csv.open('w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['model_id','marca','modelo'])
        for r in unresolved_rows:
            cw.writerow(r)

    print('Backfill tipo_equipo completo')
    print('Total modelos considerados:', total)
    print('Actualizados por Access CSV:', updated_access)
    print('Actualizados por heuristica:', updated_heur)
    print('Sin resolver:', skipped)
    print('CSV:', out_csv)
    print('Pendientes CSV:', pend_csv)


if __name__ == '__main__':
    main()
