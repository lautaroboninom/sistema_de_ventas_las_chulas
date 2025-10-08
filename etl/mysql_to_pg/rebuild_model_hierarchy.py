"""
Reconstruye model_hierarchy (y series faltantes si es necesario) para asociar modelos a los nuevos tipos importados.

Reglas
 - Para cada models(marca_id, nombre, tipo_equipo[, variante]):
    * Buscar tipo_id en marca_tipos_equipo (UPPER(TRIM(nombre))). Si no existe, crear (activo=TRUE).
    * Buscar serie_id en marca_series (por marca_id, tipo_id, UPPER(TRIM(nombre))). Si no existe, crear (activo=TRUE).
    * Upsert en model_hierarchy(model_id -> marca_id, tipo_id, serie_id, [variante_id si existe por nombre]).

Imprime: creados_series, creados_mh, vinculadas_variantes
"""

from __future__ import annotations

import os
import psycopg


def env(name: str, default: str = "") -> str:
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
    created_series = 0
    created_mh = 0
    linked_vars = 0
    with connect_pg() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT id, marca_id, nombre, COALESCE(NULLIF(TRIM(tipo_equipo),''),'SIN TIPO') AS tipo, NULLIF(TRIM(COALESCE(variante,'')),'') AS variante FROM models ORDER BY id")
                models = cur.fetchall()
                for mid, marca_id, nombre, tipo, variante in models:
                    # tipo
                    cur.execute("SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, tipo))
                    row = cur.fetchone()
                    if row:
                        tipo_id = int(row[0])
                    else:
                        cur.execute("INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE) RETURNING id", (marca_id, tipo))
                        tipo_id = int(cur.fetchone()[0])
                    # serie
                    cur.execute("SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, tipo_id, nombre))
                    row = cur.fetchone()
                    if row:
                        serie_id = int(row[0])
                    else:
                        cur.execute("INSERT INTO marca_series(marca_id, tipo_id, nombre, activo) VALUES (%s,%s,%s,TRUE) RETURNING id", (marca_id, tipo_id, nombre))
                        serie_id = int(cur.fetchone()[0])
                        created_series += 1
                    # variante
                    var_id = None
                    if variante:
                        cur.execute("SELECT id FROM marca_series_variantes WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (marca_id, tipo_id, serie_id, variante))
                        r2 = cur.fetchone()
                        if r2:
                            var_id = int(r2[0])
                    # upsert mh
                    cur.execute("SELECT 1 FROM model_hierarchy WHERE model_id=%s", (mid,))
                    exists = cur.fetchone()
                    full = f"{tipo.strip()} | {str(nombre).strip()}{(' ' + variante) if variante else ''}"
                    if exists:
                        cur.execute("UPDATE model_hierarchy SET marca_id=%s, tipo_id=%s, serie_id=%s, variante_id=%s, full_name=%s WHERE model_id=%s", (marca_id, tipo_id, serie_id, var_id, full, mid))
                    else:
                        cur.execute("INSERT INTO model_hierarchy(model_id, marca_id, tipo_id, serie_id, variante_id, full_name) VALUES (%s,%s,%s,%s,%s,%s)", (mid, marca_id, tipo_id, serie_id, var_id, full))
                        created_mh += 1
                    if var_id:
                        linked_vars += 1
        conn.commit()
    print("created_series=", created_series, "created_model_hierarchy=", created_mh, "linked_variants=", linked_vars)


if __name__ == '__main__':
    main()

