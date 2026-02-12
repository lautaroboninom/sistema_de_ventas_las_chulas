"""
Corrige 'Sin Información' (o vacío) en marca/modelo de devices en Postgres,
buscando primero en Access (Servicio.Marca/Modelo por OS más reciente del device)
y si no, en MySQL (devices -> marcas/models).

Genera reporte: outputs/fix_sin_informacion_report.csv
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import psycopg  # type: ignore
import pymysql  # type: ignore

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None


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


def connect_access():
    assert pyodbc is not None, "pyodbc no disponible para Access"
    db_path = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={db_path};", autocommit=True)


def norm(s: Optional[str]) -> str:
    if not s:
        return ''
    s2 = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s2 = s2.lower().strip()
    s2 = re.sub(r"\s+", " ", s2)
    return s2


def is_placeholder(s: Optional[str]) -> bool:
    n = norm(s)
    return (not n) or n.startswith('sin informacion') or n.startswith('sin informacion') or n == 's/i'


def get_latest_os_for_device(cur_pg, device_id: int) -> Optional[int]:
    cur_pg.execute("SELECT id FROM ingresos WHERE device_id=%s ORDER BY id DESC LIMIT 1", (device_id,))
    r = cur_pg.fetchone()
    return int(r[0]) if r else None


def ensure_brand(cur_pg, nombre: str) -> int:
    cur_pg.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (nombre,))
    r = cur_pg.fetchone()
    if r:
        return int(r[0])
    cur_pg.execute("INSERT INTO marcas(nombre) VALUES (%s) RETURNING id", (nombre,))
    return int(cur_pg.fetchone()[0])


def ensure_model(cur_pg, marca_id: int, nombre: str) -> int:
    cur_pg.execute("SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (marca_id, nombre))
    r = cur_pg.fetchone()
    if r:
        return int(r[0])
    cur_pg.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (marca_id, nombre))
    return int(cur_pg.fetchone()[0])


def build_mysql_device_names(my, device_ids: List[int]) -> Dict[int, Tuple[str, str]]:
    out: Dict[int, Tuple[str, str]] = {}
    if not device_ids:
        return out
    with my.cursor() as cur:
        chunks = [device_ids[i:i+1000] for i in range(0, len(device_ids), 1000)]
        for ch in chunks:
            fmt = ','.join(['%s'] * len(ch))
            cur.execute(
                f"""
                SELECT d.id AS device_id, COALESCE(b.nombre,'') AS marca, COALESCE(mo.nombre,'') AS modelo
                FROM devices d
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models mo ON mo.id=d.model_id
                WHERE d.id IN ({fmt})
                """,
                ch,
            )
            for r in cur.fetchall():
                out[int(r['device_id'])] = ((r['marca'] or '').strip(), (r['modelo'] or '').strip())
    return out


def main():
    out_csv = os.path.join('outputs', 'fix_sin_informacion_report.csv')
    os.makedirs('outputs', exist_ok=True)

    pg = connect_pg()
    my = connect_mysql()
    acc = None
    try:
        try:
            acc = connect_access() if pyodbc is not None else None
        except Exception:
            acc = None

        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT d.id AS device_id, COALESCE(b.nombre,''), COALESCE(mo.nombre,'')
                FROM devices d
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models mo ON mo.id=d.model_id
                """
            )
            dev_rows = cur.fetchall()

        # Filtrar a corregir
        to_fix: List[Tuple[int, str, str]] = []
        for (did, marca_nom, modelo_nom) in dev_rows:
            if is_placeholder(marca_nom) or is_placeholder(modelo_nom):
                to_fix.append((int(did), str(marca_nom or ''), str(modelo_nom or '')))

        # Pre-cargar nombres desde MySQL para estos devices
        my_map = build_mysql_device_names(my, [d for d, _, _ in to_fix])
        acc_cur = acc.cursor() if acc is not None else None

        updated = 0
        unchanged = 0
        rows_out: List[List[str]] = []

        with pg.transaction():
            with pg.cursor() as cur_pg:
                for device_id, old_marca, old_modelo in to_fix:
                    new_marca = ''
                    new_modelo = ''
                    source = ''
                    # 1) Access por OS
                    if acc_cur is not None:
                        os_id = get_latest_os_for_device(cur_pg, device_id)
                        if os_id is not None:
                            try:
                                acc_cur.execute("SELECT Marca, Modelo FROM [Servicio] WHERE Id=?", (int(os_id),))
                                a = acc_cur.fetchone()
                            except Exception:
                                a = None
                            if a:
                                m1 = (a[0] or '').strip()
                                m2 = (a[1] or '').strip()
                                if not is_placeholder(m1):
                                    new_marca = m1
                                if not is_placeholder(m2):
                                    new_modelo = m2
                                if new_marca or new_modelo:
                                    source = 'access'
                    # 2) Fallback MySQL
                    if not source:
                        mm = my_map.get(device_id)
                        if mm:
                            m1, m2 = mm
                            if not is_placeholder(m1):
                                new_marca = new_marca or m1
                            if not is_placeholder(m2):
                                new_modelo = new_modelo or m2
                            if new_marca or new_modelo:
                                source = 'mysql'

                    if not source:
                        unchanged += 1
                        rows_out.append([str(device_id), old_marca, old_modelo, '', '', ''])
                        continue

                    # Asegurar marca/model en PG
                    # Si alguno falta, conservar el existente que no sea placeholder
                    if is_placeholder(old_marca) and new_marca:
                        brand_id = ensure_brand(cur_pg, new_marca)
                    else:
                        # mantener marca actual si válida; si es placeholder y no obtuvimos nueva, no tocamos
                        brand_id = None
                        if not is_placeholder(old_marca):
                            cur_pg.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (old_marca,))
                            r = cur_pg.fetchone()
                            if r:
                                brand_id = int(r[0])
                    # decidir modelo
                    model_id = None
                    if is_placeholder(old_modelo) and new_modelo:
                        if brand_id is None:
                            # intentar con marca actual del device (puede ser placeholder; buscamos id real)
                            cur_pg.execute("SELECT marca_id FROM devices WHERE id=%s", (device_id,))
                            r = cur_pg.fetchone()
                            if r and r[0] is not None:
                                brand_id = int(r[0])
                        if brand_id is None and new_marca:
                            brand_id = ensure_brand(cur_pg, new_marca)
                        if brand_id is not None:
                            model_id = ensure_model(cur_pg, brand_id, new_modelo)

                    # aplicar updates en device
                    did_update = False
                    if brand_id is not None:
                        cur_pg.execute("UPDATE devices SET marca_id=%s WHERE id=%s", (brand_id, device_id))
                        did_update = did_update or (cur_pg.rowcount > 0)
                    if model_id is not None:
                        cur_pg.execute("UPDATE devices SET model_id=%s WHERE id=%s", (model_id, device_id))
                        did_update = did_update or (cur_pg.rowcount > 0)
                    if did_update:
                        updated += 1
                        rows_out.append([str(device_id), old_marca, old_modelo, new_marca, new_modelo, source])
                    else:
                        unchanged += 1
                        rows_out.append([str(device_id), old_marca, old_modelo, new_marca, new_modelo, source or ''])
        pg.commit()

        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['device_id','old_marca','old_modelo','new_marca','new_modelo','source'])
            for r in rows_out:
                cw.writerow(r)
        print('Fix Sin Información completo')
        print('Devices a revisar:', len(to_fix))
        print('Actualizados:', updated)
        print('Sin cambio:', unchanged)
        print('CSV:', out_csv)

    finally:
        try:
            pg.close()
        except Exception:
            pass
        try:
            my.close()
        except Exception:
            pass
        try:
            if acc is not None:
                acc.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

