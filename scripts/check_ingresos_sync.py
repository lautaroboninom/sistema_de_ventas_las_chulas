import os
import sys
from typing import Dict, Tuple, List, Any

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


def fetch_mysql_counts(my) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    with my.cursor() as cur:
        for table in [
            "ingresos",
            "quotes",
            "quote_items",
            "ingreso_media",
            "ingreso_events",
            "ingreso_accesorios",
            "handoffs",
            "devices",
        ]:
            cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
            counts[table] = int(cur.fetchone()["c"])  # type: ignore[index]
    return counts


def fetch_pg_counts(pg) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    with pg.cursor() as cur:
        for table in [
            "ingresos",
            "quotes",
            "quote_items",
            "ingreso_media",
            "ingreso_events",
            "ingreso_accesorios",
            "handoffs",
            "devices",
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cur.fetchone()[0])
    return counts


def fetch_mysql_ingreso_ids(my) -> List[int]:
    with my.cursor() as cur:
        cur.execute("SELECT id FROM ingresos ORDER BY id")
        return [int(r["id"]) for r in cur.fetchall()]  # type: ignore[index]


def fetch_pg_ingreso_ids(pg) -> List[int]:
    with pg.cursor() as cur:
        cur.execute("SELECT id FROM ingresos ORDER BY id")
        return [int(r[0]) for r in cur.fetchall()]


def pg_referential_checks(pg) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM ingresos i
            LEFT JOIN devices d ON d.id = i.device_id
            WHERE i.device_id IS NOT NULL AND d.id IS NULL
            """
        )
        stats["ingresos_invalid_device_fk"] = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(*)
            FROM ingresos i
            LEFT JOIN users u ON u.id = i.asignado_a
            WHERE i.asignado_a IS NOT NULL AND u.id IS NULL
            """
        )
        stats["ingresos_invalid_asignado_fk"] = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(*)
            FROM ingresos i
            LEFT JOIN users u ON u.id = i.recibido_por
            WHERE i.recibido_por IS NOT NULL AND u.id IS NULL
            """
        )
        stats["ingresos_invalid_recibido_fk"] = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(*)
            FROM ingresos i
            LEFT JOIN locations l ON l.id = i.ubicacion_id
            WHERE i.ubicacion_id IS NOT NULL AND l.id IS NULL
            """
        )
        stats["ingresos_invalid_location_fk"] = int(cur.fetchone()[0])

        # Campos críticos nulos
        cur.execute("SELECT COUNT(*) FROM ingresos WHERE estado IS NULL")
        stats["ingresos_estado_null"] = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM ingresos WHERE fecha_ingreso IS NULL")
        stats["ingresos_fecha_ingreso_null"] = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM ingresos WHERE fecha_creacion IS NULL")
        stats["ingresos_fecha_creacion_null"] = int(cur.fetchone()[0])
    return stats


def main():
    my = connect_mysql()
    pg = connect_pg()
    try:
        my_counts = fetch_mysql_counts(my)
        pg_counts = fetch_pg_counts(pg)

        my_ids = set(fetch_mysql_ingreso_ids(my))
        pg_ids = set(fetch_pg_ingreso_ids(pg))
        missing_in_pg = sorted(list(my_ids - pg_ids))
        extra_in_pg = sorted(list(pg_ids - my_ids))

        ref = pg_referential_checks(pg)

        print("=== Conteos (MySQL vs Postgres) ===")
        for k in ["ingresos","quotes","quote_items","ingreso_events","ingreso_accesorios","handoffs","ingreso_media","devices"]:
            print(f"{k:18s}  mysql={my_counts.get(k,0):6d}   pg={pg_counts.get(k,0):6d}   diff={pg_counts.get(k,0)-my_counts.get(k,0):6d}")

        print("\n=== Ingresos faltantes en PG (ids) ===", len(missing_in_pg))
        print(" ".join(str(x) for x in missing_in_pg[:50]))
        print("..." if len(missing_in_pg) > 50 else "")

        print("\n=== Ingresos extra en PG (ids no están en MySQL) ===", len(extra_in_pg))
        print(" ".join(str(x) for x in extra_in_pg[:50]))
        print("..." if len(extra_in_pg) > 50 else "")

        print("\n=== Chequeos referenciales en PG ===")
        for k, v in ref.items():
            print(f"{k:34s}: {v}")

        # Muestra de ingresos con FKs rotas
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.device_id, i.asignado_a, i.recibido_por, i.ubicacion_id
                FROM ingresos i
                LEFT JOIN devices d ON d.id = i.device_id
                WHERE i.device_id IS NOT NULL AND d.id IS NULL
                ORDER BY i.id ASC LIMIT 10
                """
            )
            rows = cur.fetchall()
            if rows:
                print("\nEjemplos device FK inválida:")
                for r in rows:
                    print(r)

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

