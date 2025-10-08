from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Optional

import psycopg  # type: ignore
import pyodbc   # type: ignore

ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
OUT_CSV = Path('outputs/migracion_leftovers_after_resolve.csv')


def connect_pg():
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def connect_access():
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};", autocommit=True)


def get_customer_id(cur_pg, razon_social: str) -> int:
    cur_pg.execute("SELECT id FROM customers WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s)) LIMIT 1", (razon_social,))
    r = cur_pg.fetchone()
    if r:
        return int(r[0])
    cur_pg.execute("INSERT INTO customers(razon_social) VALUES (%s) RETURNING id", (razon_social,))
    return int(cur_pg.fetchone()[0])


def name_from_cod(acc_cur, cod: str) -> Optional[str]:
    acc_cur.execute("SELECT NombreEmpresa FROM [Clientes] WHERE CodEmpresa=?", (cod,))
    b = acc_cur.fetchone()
    return (b[0] or '').strip() if b else None


def build_serial_index(acc_cur):
    # Crea un índice: serial_normalizado -> (fecha_ingreso, cod)
    idx = {}
    try:
        acc_cur.execute("SELECT CodEmpresa, NumeroSerie, [Fecha Ingreso] FROM [Servicio] WHERE NumeroSerie IS NOT NULL")
    except Exception:
        acc_cur.execute("SELECT CodEmpresa, NumeroSerie FROM [Servicio] WHERE NumeroSerie IS NOT NULL")
        rows = acc_cur.fetchall()
        for cod, ns in rows:
            nsn = ''.join(str(ns or '').strip().split()).upper()
            if not nsn:
                continue
            # sin fecha, conservar primer valor
            if nsn not in idx:
                idx[nsn] = (None, str(cod or '').strip())
        return idx
    rows = acc_cur.fetchall()
    for cod, ns, fe in rows:
        nsn = ''.join(str(ns or '').strip().split()).upper()
        if not nsn:
            continue
        cur_best = idx.get(nsn)
        if cur_best is None or (fe is not None and (cur_best[0] is None or fe > cur_best[0])):
            idx[nsn] = (fe, str(cod or '').strip())
    return idx


def main():
    acc = connect_access()
    acc_cur = acc.cursor()
    fixed = 0
    unresolved = []

    with connect_pg() as cn:
        with cn.cursor() as cur:
            serial_idx = build_serial_index(acc_cur)
            cur.execute(
                """
                SELECT i.id, d.id AS device_id, d.numero_serie
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                WHERE UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%'
                ORDER BY i.id ASC
                """
            )
            rows = cur.fetchall()
            for (os_id, device_id, numero_serie) in rows:
                nsn = ''.join(str(numero_serie or '').strip().split()).upper()
                cod = serial_idx.get(nsn, (None, None))[1] if nsn else None
                if cod:
                    name = name_from_cod(acc_cur, cod)
                    if name:
                        cid = get_customer_id(cur, name)
                        cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (cid, device_id))
                        fixed += 1
                    else:
                        unresolved.append((os_id, device_id, numero_serie, cod, None))
                else:
                    unresolved.append((os_id, device_id, numero_serie, None, None))
            # Segundo intento: por historial del mismo device en PG
            still = []
            for (os_id, device_id, numero_serie, cod, name) in unresolved:
                cur.execute(
                    """
                    SELECT c.razon_social
                    FROM ingresos i2
                    JOIN devices d2 ON d2.id=i2.device_id
                    JOIN customers c ON c.id=d2.customer_id
                    WHERE d2.id=%s AND UPPER(TRIM(c.razon_social)) NOT LIKE %s
                    ORDER BY i2.id DESC LIMIT 1
                    """,
                    (device_id, 'MIGRACION%')
                )
                row = cur.fetchone()
                if row:
                    cid = get_customer_id(cur, row[0])
                    cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (cid, device_id))
                    fixed += 1
                else:
                    still.append((os_id, device_id, numero_serie, cod, name))
            unresolved = still
        cn.commit()

    # Exportar pendientes
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open('w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['os_id','device_id','numero_serie','cod_empresa_encontrado','cliente_nombre'])
        for r in unresolved:
            cw.writerow(r)

    print(f"Corregidos por número de serie: {fixed}")
    print(f"Pendientes: {len(unresolved)} -> {OUT_CSV}")


if __name__ == '__main__':
    main()
