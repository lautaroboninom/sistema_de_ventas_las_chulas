"""
Importa variantes (marca_series_variantes) desde MySQL hacia PostgreSQL y
actualiza model_hierarchy.variante_id cuando exista el modelo.

Origen MySQL (contenedor 'sepid-mysql' expone 3306 en host):
  MYSQL_HOST=127.0.0.1, MYSQL_PORT=3306, MYSQL_DB=servicio_tecnico,
  MYSQL_USER=sepid, MYSQL_PASSWORD=supersegura (o variables del entorno)

Destino PostgreSQL: POSTGRES_* por entorno (.env / compose) o variables locales.

Uso:
  python etl/mysql_to_pg/import_variantes_from_mysql.py
"""

from __future__ import annotations

import os
from typing import Any, List, Tuple

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
                SELECT m.nombre AS marca, mt.nombre AS tipo, ms.nombre AS serie, mv.nombre AS variante
                FROM marca_series_variantes mv
                JOIN marca_series ms ON ms.id = mv.serie_id AND ms.marca_id = mv.marca_id AND ms.tipo_id = mv.tipo_id
                JOIN marca_tipos_equipo mt ON mt.id = mv.tipo_id AND mt.marca_id = mv.marca_id
                JOIN marcas m ON m.id = mv.marca_id
                ORDER BY m.nombre, mt.nombre, ms.nombre, mv.nombre
                """
            )
            variantes = mcur.fetchall()

        with pg.transaction():
            with pg.cursor() as cur:
                for r in variantes:
                    marca = (r["marca"] or "").strip()
                    tipo = (r["tipo"] or "").strip() or "SIN TIPO"
                    serie = (r["serie"] or "").strip()
                    variante = (r["variante"] or "").strip()
                    if not marca or not serie or not variante:
                        continue
                    # Marcas
                    marca_id = get_or_create(
                        cur,
                        "marcas",
                        "UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                        [marca],
                        ["nombre"],
                        [marca],
                    )
                    # Tipo por marca
                    cur.execute(
                        "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                        (marca_id, tipo),
                    )
                    row = cur.fetchone()
                    if row:
                        tipo_id = int(row[0])
                    else:
                        cur.execute(
                            "INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE) RETURNING id",
                            (marca_id, tipo),
                        )
                        tipo_id = int(cur.fetchone()[0])
                    # Serie (modelo) por tipo
                    serie_id = get_or_create(
                        cur,
                        "marca_series",
                        "marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                        [marca_id, tipo_id, serie],
                        ["marca_id", "tipo_id", "nombre", "activo"],
                        [marca_id, tipo_id, serie, True],
                    )
                    # Variante
                    variante_id = get_or_create(
                        cur,
                        "marca_series_variantes",
                        "marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                        [marca_id, tipo_id, serie_id, variante],
                        ["marca_id", "tipo_id", "serie_id", "nombre", "activo"],
                        [marca_id, tipo_id, serie_id, variante, True],
                    )
                    # Vincular a model_hierarchy si existe model para esa serie
                    cur.execute(
                        "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
                        (marca_id, serie),
                    )
                    mrow = cur.fetchone()
                    if mrow:
                        mid = int(mrow[0])
                        cur.execute(
                            "UPDATE model_hierarchy SET variante_id=%s, full_name=%s WHERE model_id=%s",
                            (variante_id, f"{tipo} | {serie} {variante}", mid),
                        )
        pg.commit()
        print(f"Importadas {len(variantes)} variantes desde MySQL")
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

