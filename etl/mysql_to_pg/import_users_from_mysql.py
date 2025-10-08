"""
Importa usuarios desde MySQL y los replica en PostgreSQL "tal cual":
 - Inserta/actualiza por id (preserva ids de MySQL)
 - Reasigna FKs de usuarios existentes en PG con el mismo email a los ids de MySQL
 - Elimina los usuarios duplicados de PG que tenían el mismo email una vez migradas las referencias

Referencias reasignadas: ingresos.asignado_a, ingresos.recibido_por, ingreso_events.usuario_id, marcas.tecnico_id, models.tecnico_id

No borra usuarios que no existen en MySQL si no comparten email (p.ej., MIGRACION), para no romper FKs.
"""

from __future__ import annotations

import os
from typing import Dict, Any

import pymysql  # type: ignore
import psycopg


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_mysql():
    return pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306") or 3306),
        user=env("MYSQL_USER", "root"),
        password=env("MYSQL_PASSWORD", ""),
        database=env("MYSQL_DATABASE", env("MYSQL_DB", "servicio_tecnico")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def main():
    my = connect_mysql()
    pg = connect_pg()
    inserted = 0
    updated = 0
    moved = 0
    deleted = 0
    try:
        # 1) Traer todos los usuarios de MySQL
        with my.cursor() as cur:
            cur.execute("SELECT id, nombre, email, hash_pw, rol, activo, perm_ingresar FROM users ORDER BY id")
            my_users = cur.fetchall()
        # mapa por email
        my_by_email: Dict[str, Dict[str, Any]] = {}
        for u in my_users:
            email = (u.get('email') or '').strip().lower()
            if email:
                my_by_email[email] = u

        with pg.transaction():
            with pg.cursor() as cur:
                # 2) Upsert por id
                for u in my_users:
                    cur.execute(
                        """
                        INSERT INTO users(id, nombre, email, hash_pw, rol, activo, perm_ingresar)
                        OVERRIDING SYSTEM VALUE
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE
                          SET nombre=EXCLUDED.nombre,
                              email=EXCLUDED.email,
                              hash_pw=EXCLUDED.hash_pw,
                              rol=EXCLUDED.rol,
                              activo=EXCLUDED.activo,
                              perm_ingresar=EXCLUDED.perm_ingresar
                        """,
                        (
                            u.get('id'), u.get('nombre'), u.get('email'), u.get('hash_pw'),
                            u.get('rol'), bool(u.get('activo')), bool(u.get('perm_ingresar')),
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        # rowcount>0 no distingue insert/update en psycopg3 en ON CONFLICT
                        pass
                # 3) Reasignar FKs y eliminar duplicados por email
                cur.execute("SELECT id, nombre, LOWER(email) FROM users")
                pg_rows = cur.fetchall()
                for uid, nombre, email in pg_rows:
                    email = (email or '').strip().lower()
                    if not email:
                        continue
                    mu = my_by_email.get(email)
                    if not mu:
                        continue
                    my_id = int(mu.get('id'))
                    if my_id == uid:
                        continue
                    # mover referencias del uid actual al my_id
                    cur.execute("UPDATE ingresos SET asignado_a=%s WHERE asignado_a=%s", (my_id, uid)); moved += cur.rowcount or 0
                    cur.execute("UPDATE ingresos SET recibido_por=%s WHERE recibido_por=%s", (my_id, uid)); moved += cur.rowcount or 0
                    cur.execute("UPDATE ingreso_events SET usuario_id=%s WHERE usuario_id=%s", (my_id, uid)); moved += cur.rowcount or 0
                    cur.execute("UPDATE marcas SET tecnico_id=%s WHERE tecnico_id=%s", (my_id, uid)); moved += cur.rowcount or 0
                    cur.execute("UPDATE models SET tecnico_id=%s WHERE tecnico_id=%s", (my_id, uid)); moved += cur.rowcount or 0
                    # borrar el usuario duplicado
                    cur.execute("DELETE FROM users WHERE id=%s", (uid,)); deleted += cur.rowcount or 0
        pg.commit()
        print(f"Usuarios importados desde MySQL. moved={moved} deleted={deleted}")
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

