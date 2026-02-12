"""
Backfill de número de serie (devices.numero_serie) en Postgres usando MySQL y como
fallback Microsoft Access (tabla Servicio.NumeroSerie por OS vinculado al device).

Pasos:
- Tomar devices en PG con numero_serie vacío o NULL.
- Rellenar desde MySQL.devices(numero_serie) por id.
- Para los que queden vacíos, intentar desde Access.Servicio por el OS (ingreso más reciente del device).

Salida: outputs/pg_serial_backfill.csv con detalle.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Tuple

import pymysql  # type: ignore
import psycopg  # type: ignore

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None


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


def connect_access():
    assert pyodbc is not None, "pyodbc no disponible para Access"
    db_path = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={db_path};", autocommit=True)


def chunked(seq: List[int], size: int = 1000):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]


def main():
    out_csv = os.path.join('outputs', 'pg_serial_backfill.csv')
    os.makedirs('outputs', exist_ok=True)

    my = connect_mysql()
    pg = connect_pg()
    acc = None
    try:
        try:
            acc = connect_access() if pyodbc is not None else None
        except Exception:
            acc = None

        # 1) Devices faltantes en PG
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM devices WHERE numero_serie IS NULL OR LENGTH(TRIM(numero_serie))=0")
            pg_missing_ids = [int(r[0]) for r in cur.fetchall()]

        updated_from_mysql = 0
        updated_from_access = 0
        rows_out: List[Tuple[int, str, str]] = []  # (device_id, source, numero_serie)

        if pg_missing_ids:
            # 2) Intento desde MySQL
            with my.cursor() as cur:
                for chunk in chunked(pg_missing_ids, 1000):
                    fmt = ','.join(['%s'] * len(chunk))
                    cur.execute(f"SELECT id, numero_serie FROM devices WHERE id IN ({fmt}) AND numero_serie IS NOT NULL AND TRIM(numero_serie)<>''", chunk)
                    for r in cur.fetchall():  # type: ignore[assignment]
                        did = int(r['id'])
                        ns = (r['numero_serie'] or '').strip()
                        if not ns:
                            continue
                        with pg.cursor() as cur_pg:
                            cur_pg.execute("UPDATE devices SET numero_serie=%s WHERE id=%s AND (numero_serie IS NULL OR LENGTH(TRIM(numero_serie))=0)", (ns, did))
                            if cur_pg.rowcount:
                                updated_from_mysql += 1
                                rows_out.append((did, 'mysql', ns))
            pg.commit()

        # 3) Fallback desde Access por OS vinculado (ingreso más reciente)
        # Recalcular pendientes
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM devices WHERE numero_serie IS NULL OR LENGTH(TRIM(numero_serie))=0")
            still_missing = [int(r[0]) for r in cur.fetchall()]

        if acc is not None and still_missing:
            acc_cur = acc.cursor()
            with pg.transaction():
                with pg.cursor() as cur_pg:
                    for did in still_missing:
                        cur_pg.execute("SELECT id FROM ingresos WHERE device_id=%s ORDER BY id DESC LIMIT 1", (did,))
                        row = cur_pg.fetchone()
                        if not row:
                            continue
                        os_id = int(row[0])
                        try:
                            acc_cur.execute("SELECT TOP 1 NumeroSerie FROM [Servicio] WHERE Id=?", (os_id,))
                            a = acc_cur.fetchone()
                        except Exception:
                            a = None
                        ns = (a[0] or '').strip() if a else ''
                        if not ns:
                            continue
                        cur_pg.execute("UPDATE devices SET numero_serie=%s WHERE id=%s AND (numero_serie IS NULL OR LENGTH(TRIM(numero_serie))=0)", (ns, did))
                        if cur_pg.rowcount:
                            updated_from_access += 1
                            rows_out.append((did, 'access', ns))
            pg.commit()

        # Resumen final
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM devices WHERE numero_serie IS NULL OR LENGTH(TRIM(numero_serie))=0")
            remaining = int(cur.fetchone()[0])

        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['device_id','source','numero_serie'])
            for did, src, ns in rows_out:
                cw.writerow([did, src, ns])

        print('Backfill serie completado')
        print('Actualizados desde MySQL:', updated_from_mysql)
        print('Actualizados desde Access:', updated_from_access)
        print('Pendientes en PG:', remaining)
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
        try:
            if acc is not None:
                acc.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

