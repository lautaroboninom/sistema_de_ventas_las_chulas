"""
Completa models.tipo_equipo (pendientes) en Postgres usando coincidencias difusas
contra el CSV de Access (etl/out/model_tipo_equipo_access.csv) y como fallback
coincidencias difusas contra MySQL.models. Opcionalmente intenta inferir por Internet
con búsqueda (DuckDuckGo) si se pasa --online.

Uso:
  python etl/fuzzy_tipo_equipo_from_access.py [--online]

Salida: outputs/fuzzy_tipo_equipo_report.csv
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import psycopg  # type: ignore
import pymysql  # type: ignore

try:
    import requests  # type: ignore
except Exception:
    requests = None

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


STOP = {'de','del','la','el','y','o','para','con','sin','modelo','model'}


def tokens(s: Optional[str]) -> List[str]:
    t = [w for w in re.split(r"[^a-z0-9]+", alnum(s)) if w]
    return [w for w in t if w not in STOP]


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


def score_match(target_brand_a: str, target_model_a: str, target_toks: List[str], rec: AccessRec) -> float:
    s = 0.0
    if target_brand_a == rec.marca_a:
        s += 0.3
    # exact model
    if target_model_a == rec.modelo_a:
        s += 0.7
        return s
    # prefix/contains
    if target_model_a and rec.modelo_a.startswith(target_model_a):
        s += 0.4
    if target_model_a and target_model_a.startswith(rec.modelo_a):
        s += 0.4
    # token overlap
    if target_toks and rec.toks:
        common = len(set(target_toks).intersection(set(rec.toks)))
        denom = max(len(set(target_toks)), 1)
        s += 0.5 * (common / denom)
    return s


def web_guess(brand: str, model: str) -> Optional[str]:
    if requests is None:
        return None
    q = f"{brand} {model}".strip()
    if not q:
        return None
    try:
        r = requests.get('https://duckduckgo.com/html/', params={'q': q}, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        text = r.text.lower()
    except Exception:
        return None
    # crude keyword mapping
    pairs = [
        (['defibrillator','desfibrilador','cardioverter'], 'CARDIODESFIBRILADOR'),
        (['multiparameter','multiparametrico','monitor multiparametrico','patient monitor','monitor'], 'MONITOR MULTIPARAMETRICO'),
        (['central monitoring','central de monitoreo'], 'CENTRAL DE MONITOREO'),
        (['oxygen concentrator','concentrador de oxigeno','concentrator'], 'CONCENTRADOR DE OXIGENO'),
        (['ventilator','respirador'], 'RESPIRADOR'),
        (['suction','aspirador'], 'ASPIRADOR'),
        (['infusion pump','feeding pump','bomba de infusion','bomba de alimentacion'], 'BOMBA DE INFUSION'),
        (['electrosurgical','electrobisturi'], 'ELECTROBISTURI'),
        (['oximeter','oximetro','spo2 monitor'], 'OXÍMETRO DE PULSO'),
        (['cpap'], 'CPAP'),
        (['bipap'], 'BPAP'),
        (['humidifier','humidificador'], 'CALENTADOR HUMIDIFICADOR'),
        (['nebulizer','nebulizador'], 'NEBULIZADOR'),
        (['capnograph','capnografo','capnography'], 'CAPNÓGRAFO'),
        (['electrocardiograph','ecg','electrocardiografo'], 'ELECTROCARDIÓGRAFO'),
    ]
    for kws, tipo in pairs:
        if any(kw in text for kw in kws):
            return tipo
    return None


def main():
    use_online = '--online' in (env('ARGS','') + ' ' + ' '.join(os.sys.argv[1:]))
    out_csv = Path('outputs/fuzzy_tipo_equipo_report.csv')
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    access_recs = load_access_records()
    pg = connect_pg()
    my = connect_mysql()
    my_map = mysql_model_map(my)

    total = 0
    updated = 0
    via_access = 0
    via_mysql = 0
    via_online = 0
    rows: List[List[str]] = []

    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, COALESCE(b.nombre,''), COALESCE(m.nombre,''), COALESCE(m.tipo_equipo,'')
            FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
            WHERE m.tipo_equipo IS NULL OR LENGTH(TRIM(m.tipo_equipo))=0
            """
        )
        pend = cur.fetchall()

    with pg.transaction():
        with pg.cursor() as cur:
            for (mid, marca, modelo, tipo) in pend:
                total += 1
                marca_a = alnum(marca)
                modelo_a = alnum(modelo)
                toks = tokens(modelo)
                # 1) Access fuzzy
                best = None
                best_s = 0.0
                for rec in access_recs:
                    s = score_match(marca_a, modelo_a, toks, rec)
                    if s > best_s:
                        best_s = s
                        best = rec
                decided = None
                src = ''
                if best and best_s >= 0.75:
                    decided = best.tipo
                    src = 'access_fuzzy'
                # 2) MySQL fuzzy
                if not decided:
                    key = (marca_a, modelo_a)
                    if key in my_map:
                        decided = my_map[key]
                        src = 'mysql_exact'
                    else:
                        # try startswith on model within same brand
                        for (mk, mm), te in my_map.items():
                            if mk == marca_a and (modelo_a and (mm.startswith(modelo_a) or modelo_a.startswith(mm))):
                                decided = te
                                src = 'mysql_fuzzy'
                                break
                # 3) online
                if not decided and use_online:
                    guess = web_guess(marca, modelo)
                    if guess:
                        decided = guess
                        src = 'online'
                if decided:
                    cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (decided, mid))
                    if cur.rowcount:
                        updated += 1
                        if src == 'access_fuzzy':
                            via_access += 1
                        elif src.startswith('mysql'):
                            via_mysql += 1
                        elif src == 'online':
                            via_online += 1
                        rows.append([str(mid), str(marca), str(modelo), decided, src])
    pg.commit()

    with out_csv.open('w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['model_id','marca','modelo','tipo_equipo','source'])
        for r in rows:
            cw.writerow(r)

    print('Fuzzy tipo_equipo:')
    print('Pendientes considerados:', total)
    print('Actualizados:', updated, '| access:', via_access, '| mysql:', via_mysql, '| online:', via_online)
    print('CSV:', str(out_csv))


if __name__ == '__main__':
    main()

