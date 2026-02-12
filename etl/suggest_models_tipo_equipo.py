"""
Genera sugerencias de tipo_equipo para modelos pendientes en PG.

Salida: outputs/models_tipo_equipo_suggestions.csv con columnas:
  model_id,marca,modelo,ingresos_count,sugerencia,fuente,confianza

No aplica cambios; usar etl/apply_model_tipo_equipo_manual.py para cargar manualmente.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg  # type: ignore
import pymysql  # type: ignore

ACCESS_CSV = Path('etl/out/model_tipo_equipo_access.csv')


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


def connect_mysql():
    return pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306") or 3306),
        user=env("MYSQL_USER", "sepid"),
        password=env("MYSQL_PASSWORD", "supersegura"),
        database=env("MYSQL_DATABASE", env("MYSQL_DB", "servicio_tecnico")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def norm(s: Optional[str]) -> str:
    if not s:
        return ''
    s2 = ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')
    s2 = s2.lower().strip()
    s2 = re.sub(r"\s+", " ", s2)
    return s2


def alnum(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(s))


def tokens(s: Optional[str]) -> List[str]:
    t = [w for w in re.split(r"[^a-z0-9]+", alnum(s)) if w]
    return t


@dataclass
class AccessRec:
    marca: str
    modelo: str
    tipo: str
    marca_a: str
    modelo_a: str
    toks: List[str]


def load_access_records() -> List[AccessRec]:
    recs: List[AccessRec] = []
    if not ACCESS_CSV.exists():
        return recs
    with ACCESS_CSV.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for r in cr:
            marca = (r.get('marca_nombre') or '').strip()
            modelo = (r.get('modelo_nombre') or '').strip()
            tipo = (r.get('tipo_equipo') or '').strip()
            if not (marca and modelo and tipo):
                continue
            recs.append(AccessRec(marca, modelo, tipo, alnum(marca), alnum(modelo), tokens(modelo)))
    return recs


def mysql_model_map(my) -> Dict[Tuple[str, str], str]:
    m: Dict[Tuple[str, str], str] = {}
    with my.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(b.nombre,'') AS marca, COALESCE(m.nombre,'') AS modelo, COALESCE(m.tipo_equipo,'') AS tipo
            FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
            WHERE m.tipo_equipo IS NOT NULL AND TRIM(m.tipo_equipo)<>''
        """)
        for r in cur.fetchall():
            mk = (alnum(r['marca']), alnum(r['modelo']))
            if mk[0] and mk[1]:
                m[mk] = (r['tipo'] or '').strip()
    return m


def score_access(target_brand_a: str, target_model_a: str, target_toks: List[str], rec: AccessRec) -> float:
    s = 0.0
    if target_brand_a == rec.marca_a:
        s += 0.3
    if target_model_a == rec.modelo_a:
        s += 0.7
        return s
    if target_model_a and rec.modelo_a.startswith(target_model_a):
        s += 0.4
    if target_model_a and target_model_a.startswith(rec.modelo_a):
        s += 0.4
    if target_toks and rec.toks:
        common = len(set(target_toks).intersection(set(rec.toks)))
        denom = max(len(set(target_toks)), 1)
        s += 0.5 * (common / denom)
    return min(s, 1.0)


def main():
    out_csv = Path('outputs/models_tipo_equipo_suggestions.csv')
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    access_recs = load_access_records()
    pg = connect_pg()
    my = connect_mysql()
    my_map = mysql_model_map(my)

    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, COALESCE(b.nombre,''), COALESCE(m.nombre,'')
            FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
            WHERE m.tipo_equipo IS NULL OR LENGTH(TRIM(m.tipo_equipo))=0
            """
        )
        pend = cur.fetchall()

    # ingresos count por modelo para priorizar
    model_counts: Dict[int, int] = {}
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT d.model_id, COUNT(*)
            FROM ingresos i JOIN devices d ON d.id=i.device_id
            WHERE d.model_id IS NOT NULL
            GROUP BY d.model_id
            """
        )
        for mid, cnt in cur.fetchall():
            model_counts[int(mid)] = int(cnt)

    rows_out: List[List[str]] = []
    for (mid, marca, modelo) in pend:
        brand_a = alnum(marca)
        model_a = alnum(modelo)
        toks = tokens(modelo)
        # Access best
        best = None
        best_s = 0.0
        for rec in access_recs:
            s = score_access(brand_a, model_a, toks, rec)
            if s > best_s:
                best_s = s
                best = rec
        sug = ''
        src = ''
        conf = 0.0
        if brand_a and model_a and (brand_a, model_a) in my_map:
            sug = my_map[(brand_a, model_a)]
            src = 'mysql_exact'
            conf = 0.95
        elif best and best_s >= 0.6:
            sug = best.tipo
            src = 'access_fuzzy'
            conf = round(best_s, 2)
        else:
            # mysql fuzzy con startswith en model dentro de misma marca
            for (mk, mm), te in my_map.items():
                if mk == brand_a and model_a and (mm.startswith(model_a) or model_a.startswith(mm)):
                    sug = te
                    src = 'mysql_fuzzy'
                    conf = 0.7
                    break
        rows_out.append([
            str(mid), str(marca), str(modelo), str(model_counts.get(int(mid), 0)), sug, src, f"{conf:.2f}"
        ])

    # ordenar por impacto y confianza
    rows_out.sort(key=lambda r: (-(int(r[3]) if str(r[3]).isdigit() else 0), -float(r[6]) ))

    with out_csv.open('w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['model_id','marca','modelo','ingresos_count','sugerencia','fuente','confianza'])
        for r in rows_out:
            cw.writerow(r)

    print('Generadas sugerencias:', len(rows_out))
    print('Archivo:', out_csv)


if __name__ == '__main__':
    main()

