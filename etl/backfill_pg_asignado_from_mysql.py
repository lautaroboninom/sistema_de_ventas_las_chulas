"""
Backfill de tecnicos asignados (ingresos.asignado_a) en Postgres usando MySQL.

Reglas:
- Mapear usuarios MySQL -> PG por email (preferido) o por nombre.
- Si no existe en PG, crear usuario con rol 'tecnico', activo TRUE, perm_ingresar FALSE.
- Actualizar ingresos en PG si difieren o están nulos.

Salida: outputs/pg_asignado_backfill.csv con detalle de cambios.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, Tuple, Optional

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


def simp(s: Optional[str]) -> str:
    s = (s or '').strip()
    return ' '.join(s.split()).lower()


def load_mysql_users(my) -> Dict[int, Tuple[str, str]]:
    with my.cursor() as cur:
        cur.execute("SELECT id, nombre, email FROM users")
        return {int(r['id']): ((r['nombre'] or '').strip(), (r['email'] or '').strip()) for r in cur.fetchall()}  # type: ignore[index]


def load_pg_user_indexes(pg_cur):
    pg_cur.execute("SELECT id, nombre, email FROM users")
    by_email: Dict[str, int] = {}
    by_name: Dict[str, int] = {}
    for (uid, nombre, email) in pg_cur.fetchall():
        if email:
            by_email[simp(email)] = int(uid)
        if nombre:
            by_name[simp(nombre)] = int(uid)
    return by_email, by_name


def ensure_pg_user(pg_cur, nombre: str, email: str, by_email: Dict[str, int], by_name: Dict[str, int]) -> int:
    key_email = simp(email)
    key_name = simp(nombre)
    # 1) email exacto
    if key_email and key_email in by_email:
        return by_email[key_email]
    # 2) nombre
    if key_name and key_name in by_name:
        return by_name[key_name]
    # 3) crear
    nombre_i = nombre or (email.split('@')[0] if email else 'Tecnico')
    email_i = email or f"legacy+{nombre_i.replace(' ','_')}@local.invalid"
    pg_cur.execute(
        "INSERT INTO users(nombre, email, rol, activo, perm_ingresar) VALUES (%s,%s,%s,TRUE,FALSE) RETURNING id",
        (nombre_i, email_i, 'tecnico'),
    )
    new_id = int(pg_cur.fetchone()[0])
    if key_email:
        by_email[key_email] = new_id
    if key_name:
        by_name[key_name] = new_id
    return new_id


def main():
    out_path = os.path.join('outputs', 'pg_asignado_backfill.csv')
    os.makedirs('outputs', exist_ok=True)

    my = connect_mysql()
    pg = connect_pg()
    updated = 0
    skipped_equal = 0
    missing_pg_ingreso = 0
    total_considered = 0
    created_users = 0
    rows_out = []
    try:
        my_users = load_mysql_users(my)
        with pg.cursor() as cur_pg:
            by_email, by_name = load_pg_user_indexes(cur_pg)
        with my.cursor() as cur:
            cur.execute("SELECT id AS ingreso_id, asignado_a FROM ingresos WHERE asignado_a IS NOT NULL")
            my_rows = cur.fetchall()
        with pg.transaction():
            with pg.cursor() as cur_pg:
                for r in my_rows:
                    total_considered += 1
                    iid = int(r['ingreso_id'])  # type: ignore[index]
                    my_uid = int(r['asignado_a'])  # type: ignore[index]
                    my_nombre, my_email = my_users.get(my_uid, ('',''))

                    # chequear que ingreso exista en PG
                    cur_pg.execute("SELECT asignado_a FROM ingresos WHERE id=%s", (iid,))
                    got = cur_pg.fetchone()
                    if not got:
                        missing_pg_ingreso += 1
                        rows_out.append([iid, my_uid, my_nombre, my_email, '', '', 'pg_missing'])
                        continue
                    pg_current = got[0]

                    target_uid = ensure_pg_user(cur_pg, my_nombre, my_email, by_email, by_name)
                    # detectar si se creó
                    if target_uid not in by_email.values() and target_uid not in by_name.values():
                        created_users += 1
                    if pg_current is not None and int(pg_current) == target_uid:
                        skipped_equal += 1
                        rows_out.append([iid, my_uid, my_nombre, my_email, target_uid, 'equal', ''])
                        continue
                    cur_pg.execute("UPDATE ingresos SET asignado_a=%s WHERE id=%s", (target_uid, iid))
                    updated += 1
                    rows_out.append([iid, my_uid, my_nombre, my_email, target_uid, 'updated', ''])
        pg.commit()
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        cw = csv.writer(f)
        cw.writerow(['ingreso_id','mysql_user_id','mysql_nombre','mysql_email','pg_user_id','action','notes'])
        for row in rows_out:
            cw.writerow(row)

    print('Backfill completo')
    print('Ingresos considerados:', total_considered)
    print('Actualizados:', updated)
    print('Iguales:', skipped_equal)
    print('PG faltantes:', missing_pg_ingreso)
    print('CSV:', out_path)


if __name__ == '__main__':
    main()

