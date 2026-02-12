"""
Importa modelos y tipos de equipo desde MySQL a PostgreSQL mapeando marcas por nombre.

Requiere: PyMySQL y psycopg instalados.

Uso:
  MYSQL_* y POSTGRES_* en entorno y:
  python etl/mysql_to_pg/import_models_types_from_mysql.py
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

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


def get_or_create(cur, table: str, where_sql: str, where_params: List[Any], insert_cols: List[str], insert_vals: List[Any]) -> int:
    cur.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", where_params)
    row = cur.fetchone()
    if row:
        return int(row[0])
    cols = ", ".join(insert_cols)
    placeholders = ", ".join(["%s"] * len(insert_cols))
    cur.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING RETURNING id",
        insert_vals,
    )
    got = cur.fetchone()
    if got:
        return int(got[0])
    cur.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", where_params)
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No se pudo crear fila en {table}")
    return int(row[0])


def main():
    my = connect_mysql()
    pg = connect_pg()
    try:
        with my.cursor() as mcur:
            mcur.execute(
                """
                SELECT m.id AS model_id, m.nombre AS modelo, m.tipo_equipo AS tipo_equipo, b.nombre AS marca
                FROM models m
                JOIN marcas b ON b.id = m.marca_id
                ORDER BY b.nombre, m.nombre
                """
            )
            rows = mcur.fetchall()

        with pg.transaction():
            with pg.cursor() as cur:
                for r in rows:
                    modelo = (r["modelo"] or "").strip()
                    marca = (r["marca"] or "").strip()
                    tipo = (r["tipo_equipo"] or "").strip() or "SIN TIPO"
                    if not modelo or not marca:
                        continue
                    marca_id = get_or_create(cur, "marcas", "UPPER(TRIM(nombre))=UPPER(TRIM(%s))", [marca], ["nombre"], [marca])

                    # upsert model (marca_id, nombre)
                    cur.execute("SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, modelo))
                    row = cur.fetchone()
                    if row:
                        mid = int(row[0])
                        cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, mid))
                    else:
                        cur.execute(
                            "INSERT INTO models(marca_id, nombre, tipo_equipo) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
                            (marca_id, modelo, tipo),
                        )
                        got = cur.fetchone()
                        if got:
                            mid = int(got[0])
                        else:
                            cur.execute("SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, modelo))
                            mid = int(cur.fetchone()[0])

                    tipo_id = get_or_create(cur, "marca_tipos_equipo", "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", [marca_id, tipo], ["marca_id", "nombre", "activo"], [marca_id, tipo, True])
                    serie_id = get_or_create(cur, "marca_series", "marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", [marca_id, tipo_id, modelo], ["marca_id", "tipo_id", "nombre", "activo"], [marca_id, tipo_id, modelo, True])
                    # model_hierarchy sin variante
                    cur.execute("SELECT id FROM model_hierarchy WHERE model_id=%s", (mid,))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO model_hierarchy(model_id, marca_id, tipo_id, serie_id, full_name) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (mid, marca_id, tipo_id, serie_id, f"{tipo} | {modelo}"),
                        )
        pg.commit()
        print(f"Importados/actualizados {len(rows)} modelos y tipos")
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

