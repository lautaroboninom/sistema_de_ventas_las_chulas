"""
Corrige cliente y ubicación de ingresos en Postgres usando Access (Servicio/Clientes)
y CSV de MySQL ingresos.csv para mapear ubicaciones por OS.

Pasos:
- Lee Access Servicio (Id, CodEmpresa) y Clientes (CodEmpresa -> NombreEmpresa)
- Lee CSV MySQL ingresos.csv (id -> ubicacion_id)
- Deduce mapeo ubicacion_id->locations PG: 1->'Taller', 5->'Sarmiento', 20->'Estantería de Alquiler'
- Para cada ingreso en PG:
  * Si el cliente es 'MIGRACION', re-asigna device.customer al cliente según Access
  * Actualiza ubicacion_id según CSV (si hay mapeo)

Conexión PG: usa host=localhost port=5433 por defecto (docker-compose expone 5433)
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import psycopg  # type: ignore

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None

ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
MYSQL_INGRESOS_CSV = Path('backups/mysql_20251001_155856/ingresos.csv')


def connect_pg():
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def connect_access():
    assert pyodbc is not None, "pyodbc no está disponible para leer Access"
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};", autocommit=True)


def load_access_mappings() -> Tuple[Dict[int, str], Dict[int, str]]:
    """Devuelve:
    - os_to_cod: OS (Id) -> CodEmpresa
    - cod_to_name: CodEmpresa -> NombreEmpresa
    """
    cn = connect_access()
    cur = cn.cursor()
    os_to_cod: Dict[int, str] = {}
    cur.execute("SELECT Id, CodEmpresa FROM [Servicio]")
    for row in cur.fetchall():
        try:
            os_id = int(row[0])
        except Exception:
            continue
        cod = (row[1] or '').strip().upper()
        if cod:
            os_to_cod[os_id] = cod
    cod_to_name: Dict[int, str] = {}
    # Clientes: usar CodEmpresa como clave -> NombreEmpresa
    cur.execute("SELECT CodEmpresa, NombreEmpresa FROM [Clientes]")
    c_map: Dict[str, str] = {}
    for row in cur.fetchall():
        cod = (row[0] or '').strip().upper()
        nom = (row[1] or '').strip()
        if cod and nom:
            c_map[cod] = nom
    cn.close()
    return os_to_cod, c_map


def load_mysql_ubicaciones() -> Dict[int, int]:
    idx: Dict[int, int] = {}
    if not MYSQL_INGRESOS_CSV.exists():
        return idx
    with MYSQL_INGRESOS_CSV.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for row in cr:
            try:
                os_id = int(row['id'])
            except Exception:
                continue
            u = row.get('ubicacion_id')
            try:
                uid = int(u) if u else None
            except Exception:
                uid = None
            if uid is not None:
                idx[os_id] = uid
    return idx


def ensure_customer_id(cur_pg, razon_social: str) -> int:
    cur_pg.execute("SELECT id FROM customers WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s)) LIMIT 1", (razon_social,))
    row = cur_pg.fetchone()
    if row:
        return int(row[0])
    cur_pg.execute("INSERT INTO customers(razon_social) VALUES (%s) RETURNING id", (razon_social,))
    return int(cur_pg.fetchone()[0])


def get_location_ids(cur_pg) -> Dict[str, int]:
    cur_pg.execute("SELECT id, nombre FROM locations")
    return {str(n).strip().lower(): int(i) for (i, n) in cur_pg.fetchall()}


def map_mysql_loc_to_pg_id(mysql_loc_id: int, loc_name_to_id: Dict[str, int]) -> Optional[int]:
    # Deducción:
    #  1 -> Taller
    #  5 -> Sarmiento
    # 20 -> Estantería de Alquiler (usar nombre canónico si existe)
    if mysql_loc_id == 1:
        return loc_name_to_id.get('taller')
    if mysql_loc_id == 5:
        # algunos sistemas lo llamaban Sarmiento (depósito/recepción)
        # si no existe, dejar None
        return loc_name_to_id.get('sarmiento')
    if mysql_loc_id == 20:
        # Preferir nombre canónico
        return (
            loc_name_to_id.get('estantería de alquiler')
            or loc_name_to_id.get('estanteria de alquiler')
            or loc_name_to_id.get('estantería alquiler')
            or loc_name_to_id.get('estanteria alquiler')
        )
    return None


def main():
    if pyodbc is None:
        print("ERROR: pyodbc no instalado; no puedo leer Access.")
        return
    os_to_cod, cod_to_name = load_access_mappings()
    os_to_mysql_loc = load_mysql_ubicaciones()

    with connect_pg() as cn:
        with cn.cursor() as cur:
            loc_name_to_id = get_location_ids(cur)

            # Buscar ingresos con cliente MIGRACION y/o ubicacion nula
            cur.execute(
                """
                SELECT i.id, i.device_id, i.ubicacion_id, c.id AS cust_id, c.razon_social
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                WHERE (UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%')
                   OR i.ubicacion_id IS NULL
                ORDER BY i.id ASC
                """
            )
            rows = cur.fetchall()

            updates = 0
            fixed_client = 0
            fixed_loc = 0
            for (os_id, device_id, ubic_id, cust_id, cust_name) in rows:
                need_commit = False

                # 1) Cliente
                if str(cust_name).strip().upper().startswith('MIGRACION'):
                    cod = os_to_cod.get(int(os_id))
                    if cod:
                        nombre = cod_to_name.get(cod.upper())
                        if nombre:
                            new_cid = ensure_customer_id(cur, nombre)
                            # Reasignar device al nuevo customer
                            cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (new_cid, device_id))
                            fixed_client += 1
                            need_commit = True

                # 2) Ubicación
                if ubic_id is None:
                    ml = os_to_mysql_loc.get(int(os_id))
                    if ml is not None:
                        pg_loc_id = map_mysql_loc_to_pg_id(ml, loc_name_to_id)
                        if pg_loc_id is not None:
                            cur.execute("UPDATE ingresos SET ubicacion_id=%s WHERE id=%s", (pg_loc_id, os_id))
                            fixed_loc += 1
                            need_commit = True

                if need_commit:
                    updates += 1

            cn.commit()
            print(f"Ingresos evaluados: {len(rows)} | ingresos actualizados: {updates}")
            print(f"Clientes corregidos: {fixed_client} | Ubicaciones corregidas: {fixed_loc}")


if __name__ == '__main__':
    main()
