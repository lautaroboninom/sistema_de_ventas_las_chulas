"""
Completa models.tipo_equipo en Postgres usando tabla models de MySQL.

Join por nombre de marca y nombre de modelo normalizados (sin acentos, minúsculas, solo alfanuméricos) para evitar desalineación de IDs.
Solo actualiza donde tipo_equipo está NULL o vacío en PG.

Salida: outputs/model_tipo_equipo_from_mysql.csv
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from typing import Dict, Tuple, List

import pymysql  # type: ignore
import psycopg  # type: ignore


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


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


def connect_pg():
    host = env('PG_HOST', env('POSTGRES_HOST', 'localhost'))
    port = int(env('PG_PORT', env('POSTGRES_PORT', '5433')))
    db = env('PG_DB', env('POSTGRES_DB', 'servicio_tecnico'))
    user = env('PG_USER', env('POSTGRES_USER', 'sepid'))
    pw = env('PG_PASSWORD', env('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def norm_alnum(s: str) -> str:
    s2 = ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
    s2 = s2.lower().strip()
    return re.sub(r'[^a-z0-9]', '', s2)


def main():
    out_csv = os.path.join('outputs', 'model_tipo_equipo_from_mysql.csv')
    os.makedirs('outputs', exist_ok=True)

    my = connect_mysql()
    pg = connect_pg()
    updated = 0
    total = 0
    rows_out: List[List[str]] = []
    try:
        # MySQL map: (brand, model) -> tipo
        with my.cursor() as cur:
            cur.execute("""
                SELECT m.nombre AS modelo, COALESCE(m.tipo_equipo,'') AS tipo, COALESCE(b.nombre,'') AS marca
                FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
                WHERE m.tipo_equipo IS NOT NULL AND TRIM(m.tipo_equipo)<>''
            """)
            my_map: Dict[Tuple[str, str], str] = {}
            for r in cur.fetchall():
                mk = (norm_alnum(r['marca']), norm_alnum(r['modelo']))
                if mk[0] and mk[1]:
                    my_map[mk] = (r['tipo'] or '').strip()

        # PG pending models
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, COALESCE(b.nombre,''), COALESCE(m.nombre,'')
                FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
                WHERE m.tipo_equipo IS NULL OR LENGTH(TRIM(m.tipo_equipo))=0
                """
            )
            pg_models = cur.fetchall()

        if not pg_models:
            print('No hay modelos pendientes en PG')
            return

        with pg.transaction():
            with pg.cursor() as cur:
                for (mid, marca, modelo) in pg_models:
                    total += 1
                    key = (norm_alnum(marca), norm_alnum(modelo))
                    te = my_map.get(key)
                    if not te:
                        continue
                    cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (te, mid))
                    if cur.rowcount:
                        updated += 1
                        rows_out.append([str(mid), marca, modelo, te])
        pg.commit()

        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['model_id','marca','modelo','tipo_equipo'])
            for r in rows_out:
                cw.writerow(r)

        print('Backfill tipo_equipo desde MySQL completo')
        print('Modelos considerados:', total)
        print('Actualizados:', updated)
        print('CSV:', out_csv)
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

