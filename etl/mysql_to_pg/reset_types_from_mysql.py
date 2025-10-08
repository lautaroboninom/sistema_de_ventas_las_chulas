"""
Resetea solo TIPOS DE EQUIPO (y su jerarquía dependiente) en PostgreSQL tomando los datos tal cual desde MySQL.

Opera sobre:
 - marca_tipos_equipo (importa id, marca_id, nombre, activo)
 - marca_series (importa id, marca_id, tipo_id, nombre, alias, activo)
 - marca_series_variantes (importa id, marca_id, tipo_id, serie_id, nombre, activo)
 - model_hierarchy (importa id, model_id, marca_id, tipo_id, serie_id, variante_id, full_name, variant_key)

NO toca `marcas` ni `models` (se asume que ya conservan los ids de MySQL).
"""

from __future__ import annotations

import os
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
    try:
        with pg.transaction():
            with pg.cursor() as cur:
                # limpiar jerarquía dependiente (model_hierarchy -> series_variantes -> series -> tipos)
                cur.execute("DELETE FROM model_hierarchy")
                cur.execute("DELETE FROM marca_series_variantes")
                cur.execute("DELETE FROM marca_series")
                cur.execute("DELETE FROM marca_tipos_equipo")

                # importar tipos
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, marca_id, nombre, activo FROM marca_tipos_equipo ORDER BY id")
                    for r in mcur.fetchall():
                        cur.execute(
                            "INSERT INTO marca_tipos_equipo(id, marca_id, nombre, activo) OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s)",
                            (r["id"], r["marca_id"], r["nombre"], bool(r.get("activo"))),
                        )
                # importar series
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, marca_id, tipo_id, nombre, alias, activo FROM marca_series ORDER BY id")
                    for r in mcur.fetchall():
                        cur.execute(
                            """
                            INSERT INTO marca_series(id, marca_id, tipo_id, nombre, alias, activo)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s,%s)
                            """,
                            (r["id"], r["marca_id"], r["tipo_id"], r["nombre"], r.get("alias"), bool(r.get("activo"))),
                        )
                # importar variantes
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, marca_id, tipo_id, serie_id, nombre, activo FROM marca_series_variantes ORDER BY id")
                    for r in mcur.fetchall():
                        cur.execute(
                            """
                            INSERT INTO marca_series_variantes(id, marca_id, tipo_id, serie_id, nombre, activo)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s,%s)
                            """,
                            (r["id"], r["marca_id"], r["tipo_id"], r["serie_id"], r["nombre"], bool(r.get("activo"))),
                        )

                # importar model_hierarchy (si existe en MySQL)
                with my.cursor() as mcur:
                    try:
                        mcur.execute("SELECT id, model_id, marca_id, tipo_id, serie_id, variante_id, full_name, 0 as variant_key FROM model_hierarchy ORDER BY id")
                        mh = mcur.fetchall()
                    except Exception:
                        mh = []
                for r in mh:
                    cur.execute(
                        """
                        INSERT INTO model_hierarchy(id, model_id, marca_id, tipo_id, serie_id, variante_id, full_name)
                        OVERRIDING SYSTEM VALUE
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (r["id"], r["model_id"], r["marca_id"], r["tipo_id"], r["serie_id"], r.get("variante_id"), r.get("full_name")),
                    )

        pg.commit()
        print("Tipos de equipo y jerarquía importados desde MySQL")
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

