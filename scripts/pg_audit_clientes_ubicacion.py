import os
import sys
from typing import List, Tuple

import psycopg  # type: ignore

PG_HOST = os.getenv("PG_HOST", os.getenv("POSTGRES_HOST", "localhost"))
PG_PORT = int(os.getenv("PG_PORT", os.getenv("POSTGRES_PORT", "5433")))
PG_DB   = os.getenv("PG_DB", os.getenv("POSTGRES_DB", "servicio_tecnico"))
PG_USER = os.getenv("PG_USER", os.getenv("POSTGRES_USER", "sepid"))
PG_PW   = os.getenv("PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""))


def connect_pg():
    dsn = f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PW}"
    return psycopg.connect(dsn)


def main():
    with connect_pg() as cn:
        with cn.cursor() as cur:
            # Ubicaciones
            cur.execute("SELECT id, nombre FROM locations ORDER BY id")
            locs = cur.fetchall()
            print("LOCATIONS:")
            for r in locs:
                print(r)

            # Ingresos con 'MIGRACION' como cliente (por join)
            cur.execute(
                """
                SELECT i.id, d.id AS device_id, c.id AS customer_id, c.razon_social, COALESCE(l.nombre,''), i.ubicacion_id
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN locations l ON l.id=i.ubicacion_id
                WHERE UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%'
                ORDER BY i.id ASC
                LIMIT 50
                """
            )
            mig = cur.fetchall()
            print("\nMIGRACION ejemplos (id, device, cust, razon_social, ubic_nom, ubic_id):", len(mig))
            for r in mig:
                print(r)

            # Conteo total de ingresos con MIGRACION
            cur.execute(
                """
                SELECT COUNT(*) FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                WHERE UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%'
                """
            )
            print("\nTotal ingresos con cliente MIGRACION:", cur.fetchone()[0])

            # Distintos ubicaciones actual de ingresos
            cur.execute(
                """
                SELECT COALESCE(l.nombre,'(NULL)') AS ubic, COUNT(*)
                FROM ingresos i LEFT JOIN locations l ON l.id=i.ubicacion_id
                GROUP BY 1 ORDER BY 2 DESC
                """
            )
            for r in cur.fetchall():
                print("UBIC", r)


if __name__ == "__main__":
    main()

