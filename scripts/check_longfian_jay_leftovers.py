#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Verifica si existen ingresos asociados a dispositivos LONGFIAN cuyo modelo es 'JAY' sin sufijo.

Conexión: POSTGRES_* por env o defaults.
Salida: imprime conteos y muestra un muestreo de ingresos si existen.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg  # type: ignore


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


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
    cn = connect_pg()
    with cn, cn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM devices d
            JOIN models m ON m.id=d.model_id
            JOIN marcas b ON b.id=d.marca_id
            WHERE UPPER(TRIM(b.nombre))='LONGFIAN' AND UPPER(TRIM(m.nombre))='JAY'
            """
        )
        dev_count = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT i.id)
            FROM ingresos i
            JOIN devices d ON d.id=i.device_id
            JOIN models m ON m.id=d.model_id
            JOIN marcas b ON b.id=d.marca_id
            WHERE UPPER(TRIM(b.nombre))='LONGFIAN' AND UPPER(TRIM(m.nombre))='JAY'
            """
        )
        ing_count = int(cur.fetchone()[0])

        print("Devices LONGFIAN con modelo 'JAY' sin sufijo:", dev_count)
        print("Ingresos asociados a esos devices:", ing_count)

        if ing_count > 0:
            cur.execute(
                """
                SELECT i.id, d.id, COALESCE(TRIM(d.numero_serie),''), m.nombre
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN models m ON m.id=d.model_id
                JOIN marcas b ON b.id=d.marca_id
                WHERE UPPER(TRIM(b.nombre))='LONGFIAN' AND UPPER(TRIM(m.nombre))='JAY'
                ORDER BY i.id DESC LIMIT 20
                """
            )
            rows = cur.fetchall() or []
            print("Muestra (ingreso_id, device_id, numero_serie, modelo):")
            for r in rows:
                print(r[0], r[1], r[2], r[3])


if __name__ == "__main__":
    main()

