"""
Importa asignaciones de técnicos desde MySQL a PostgreSQL para marcas y modelos.

Estrategia
 - Para cada marca en MySQL con tecnico_id, buscar el usuario equivalente en PG por email o por nombre.
 - Actualizar marcas.tecnico_id en PG.
 - Repetir para models.tecnico_id.

Notas
 - No crea usuarios nuevos; si no encuentra match por email/nombre, deja NULL y reporta.
 - Requiere MYSQL_* y POSTGRES_* en el entorno.
"""

from __future__ import annotations

import os
from typing import Optional

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


def map_mysql_user_to_pg(cur_pg, my_conn, my_user_id: Optional[int]) -> Optional[int]:
    if not my_user_id:
        return None
    with my_conn.cursor() as cur:
        cur.execute("SELECT email, nombre FROM users WHERE id=%s", (my_user_id,))
        r = cur.fetchone()
    if not r:
        return None
    email = (r.get("email") or "").strip().lower()
    nombre = (r.get("nombre") or "").strip()
    if email:
        cur_pg.execute("SELECT id FROM users WHERE LOWER(email)=%s LIMIT 1", (email,))
        x = cur_pg.fetchone()
        if x:
            return int(x[0])
    if nombre:
        cur_pg.execute("SELECT id FROM users WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (nombre,))
        x = cur_pg.fetchone()
        if x:
            return int(x[0])
    return None


def main():
    my = connect_mysql()
    pg = connect_pg()
    brands_updated = 0
    models_updated = 0
    misses = 0
    try:
        with pg.transaction():
            with pg.cursor() as cur_pg:
                # marcas
                with my.cursor() as cur:
                    cur.execute("SELECT id, tecnico_id FROM marcas WHERE tecnico_id IS NOT NULL")
                    for r in cur.fetchall():
                        pg_uid = map_mysql_user_to_pg(cur_pg, my, r.get("tecnico_id"))
                        if pg_uid:
                            cur_pg.execute("UPDATE marcas SET tecnico_id=%s WHERE id=%s", (pg_uid, r["id"]))
                            brands_updated += cur_pg.rowcount or 0
                        else:
                            misses += 1
                # models
                with my.cursor() as cur:
                    cur.execute("SELECT id, tecnico_id FROM models WHERE tecnico_id IS NOT NULL")
                    for r in cur.fetchall():
                        pg_uid = map_mysql_user_to_pg(cur_pg, my, r.get("tecnico_id"))
                        if pg_uid:
                            cur_pg.execute("UPDATE models SET tecnico_id=%s WHERE id=%s", (pg_uid, r["id"]))
                            models_updated += cur_pg.rowcount or 0
                        else:
                            misses += 1
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
    print(f"Asignaciones actualizadas: marcas={brands_updated} modelos={models_updated} (no mapeados={misses})")


if __name__ == "__main__":
    main()

