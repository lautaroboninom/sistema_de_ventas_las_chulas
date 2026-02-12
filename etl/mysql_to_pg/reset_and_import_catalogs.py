"""
Resetea catálogos de marcas/modelos/variantes en PostgreSQL y los reconstruye desde MySQL,
incluyendo jerarquía por marca->tipo->serie->variante y tipo de equipo por modelo.

Pasos
 1) Desvincula devices (marca_id, model_id -> NULL)
 2) Borra model_hierarchy, marca_series_variantes, marca_series, marca_tipos_equipo, models, marcas
 3) Importa marcas (preserva IDs de MySQL), modelos (preserva IDs de MySQL)
 4) Crea marca_tipos_equipo por (marca, tipo_nombre)
 5) Crea marca_series por (marca, tipo, modelo_nombre)
 6) Crea model_hierarchy (vincula model con marca/tipo/serie y full_name)
 7) Importa variantes desde MySQL y las vincula; si el modelo tiene variante textual, la usa
 8) Reasigna devices.marca_id y devices.model_id según MySQL (por device.id)

Vars entorno: MYSQL_* y POSTGRES_* (igual que otros scripts del ETL)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

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
                # 1) desvincular devices
                cur.execute("UPDATE devices SET marca_id=NULL, model_id=NULL")
                # 2) borrar jerarquía y catálogos
                cur.execute("DELETE FROM model_hierarchy")
                cur.execute("DELETE FROM marca_series_variantes")
                cur.execute("DELETE FROM marca_series")
                cur.execute("DELETE FROM marca_tipos_equipo")
                cur.execute("DELETE FROM models")
                cur.execute("DELETE FROM marcas")

                # 3) importar marcas (preserva IDs)
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, nombre FROM marcas ORDER BY id")
                    for r in mcur.fetchall():
                        cur.execute(
                            "INSERT INTO marcas(id, nombre) OVERRIDING SYSTEM VALUE VALUES (%s,%s)",
                            (r["id"], r["nombre"]),
                        )
                # sync secuencia
                cur.execute("SELECT setval(pg_get_serial_sequence('marcas','id'), COALESCE((SELECT MAX(id) FROM marcas),0), true)")

                # 3b) importar modelos (preserva IDs) – incluye tipo_equipo y variante textual si la tiene
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, marca_id, nombre, tipo_equipo, variante FROM models ORDER BY id")
                    for r in mcur.fetchall():
                        cur.execute(
                            """
                            INSERT INTO models(id, marca_id, nombre, tipo_equipo, variante)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s)
                            """,
                            (r["id"], r["marca_id"], r["nombre"], r.get("tipo_equipo"), r.get("variante")),
                        )
                cur.execute("SELECT setval(pg_get_serial_sequence('models','id'), COALESCE((SELECT MAX(id) FROM models),0), true)")

                # 4/5/6) construir tipos y series + model_hierarchy
                # mapa (marca_id, UCASE(tipo_nombre)) -> tipo_id
                tipo_map: Dict[Tuple[int, str], int] = {}
                # mapa (marca_id, tipo_id, UCASE(serie_nombre)) -> serie_id
                serie_map: Dict[Tuple[int, int, str], int] = {}

                cur.execute("SELECT id, marca_id, nombre, tipo_equipo, variante FROM models ORDER BY id")
                for mid, marca_id, nombre, tipo_equipo, variante in cur.fetchall():
                    tname = (tipo_equipo or 'SIN TIPO').strip()
                    tkey = (int(marca_id), tname.upper())
                    tipo_id = tipo_map.get(tkey)
                    if not tipo_id:
                        cur.execute(
                            """
                            INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                            VALUES (%s,%s,TRUE)
                            ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                            RETURNING id
                            """,
                            (marca_id, tname),
                        )
                        tipo_id = int(cur.fetchone()[0])
                        tipo_map[tkey] = tipo_id
                    skey = (int(marca_id), int(tipo_id), (nombre or '').strip().upper())
                    serie_id = serie_map.get(skey)
                    if not serie_id:
                        cur.execute(
                            """
                            INSERT INTO marca_series(marca_id, tipo_id, nombre, activo)
                            VALUES (%s,%s,%s,TRUE)
                            ON CONFLICT (marca_id, tipo_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                            RETURNING id
                            """,
                            (marca_id, tipo_id, nombre),
                        )
                        serie_id = int(cur.fetchone()[0])
                        serie_map[skey] = serie_id
                    # crear/actualizar model_hierarchy
                    full = f"{tname} | {nombre}{(' ' + variante) if variante else ''}"
                    cur.execute(
                        """
                        INSERT INTO model_hierarchy(model_id, marca_id, tipo_id, serie_id, variante_id, full_name)
                        VALUES (%s,%s,%s,%s,NULL,%s)
                        ON CONFLICT (model_id) DO UPDATE SET marca_id=EXCLUDED.marca_id, tipo_id=EXCLUDED.tipo_id,
                                                            serie_id=EXCLUDED.serie_id, full_name=EXCLUDED.full_name
                        """,
                        (mid, marca_id, tipo_id, serie_id, full),
                    )

                # 7) importar variantes desde MySQL y vincular
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
                    variants = mcur.fetchall()
                for r in variants:
                    # localizar ids destino por nombres
                    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (r["marca"],))
                    b = cur.fetchone();
                    if not b: continue
                    marca_id = int(b[0])
                    cur.execute("SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, r["tipo"]))
                    t = cur.fetchone();
                    if not t: continue
                    tipo_id = int(t[0])
                    cur.execute("SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, tipo_id, r["serie"]))
                    s = cur.fetchone();
                    if not s: continue
                    serie_id = int(s[0])
                    cur.execute(
                        """
                        INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo)
                        VALUES (%s,%s,%s,%s,TRUE)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """,
                        (marca_id, tipo_id, serie_id, r["variante"]),
                    )
                    got = cur.fetchone()
                    if got:
                        var_id = int(got[0])
                        # vincular en model_hierarchy si corresponde (modelo con variante textual)
                        cur.execute(
                            """
                            UPDATE model_hierarchy mh
                               SET variante_id=%s
                             WHERE mh.marca_id=%s AND mh.tipo_id=%s AND mh.serie_id=%s
                               AND EXISTS (
                                 SELECT 1 FROM models m
                                  WHERE m.id = mh.model_id AND COALESCE(TRIM(m.variante),'')<>''
                               )
                            """,
                            (var_id, marca_id, tipo_id, serie_id),
                        )

                # 8) re-asignar devices a marca/modelo por IDs originales de MySQL (coinciden)
                with my.cursor() as mcur:
                    mcur.execute("SELECT id, marca_id, model_id FROM devices")
                    for d in mcur.fetchall():
                        cur.execute("UPDATE devices SET marca_id=%s, model_id=%s WHERE id=%s", (d["marca_id"], d["model_id"], d["id"]))

        pg.commit()
        print("Catálogos reinicializados e importados desde MySQL")
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
