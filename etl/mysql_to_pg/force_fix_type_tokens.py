"""
Fuerza la corrección de tildes/typos en los nombres de tipos de equipo en PostgreSQL y fusiona duplicados resultantes.

Reemplazos de tokens (en mayúsculas):
  OXIGENO->OXÍGENO, BATERIA->BATERÍA, BATERIAS->BATERÍAS, BATERAS->BATERÍAS, PORTATIL->PORTÁTIL

Por cada marca (marca_id):
  - Para cada tipo, calcula nombre_arreglado.
  - Si cambia, migra series al tipo con nombre_arreglado (creándolo o fusionándolo si existe) y elimina el tipo anterior.
  - Actualiza models.tipo_equipo textual para esa marca.
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


def fix_tokens(name: str) -> str:
    s = (name or '').upper()
    repl = {
        'OXIGENO': 'OXÍGENO',
        'BATERIAS': 'BATERÍAS',
        'BATERIA': 'BATERÍA',
        'BATERAS': 'BATERÍAS',
        'PORTATIL': 'PORTÁTIL',
    }
    for src, dst in repl.items():
        if src in s:
            s = s.replace(src, dst)
    return s


def main():
    fused = 0
    renamed = 0
    with connect_pg() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT marca_id FROM marca_tipos_equipo ORDER BY marca_id")
                marca_ids = [r[0] for r in cur.fetchall()]
                for mid in marca_ids:
                    cur.execute("SELECT id, nombre FROM marca_tipos_equipo WHERE marca_id=%s ORDER BY id", (mid,))
                    types = cur.fetchall()
                    for tid, nombre in types:
                        fixed = fix_tokens(nombre)
                        if fixed == nombre:
                            continue
                        # buscar o crear tipo destino con nombre fixed
                        cur.execute("SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, fixed))
                        row = cur.fetchone()
                        if row:
                            target_tid = int(row[0])
                        else:
                            cur.execute("INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE) RETURNING id", (mid, fixed))
                            target_tid = int(cur.fetchone()[0])
                        # migrar series de tid -> target_tid
                        cur.execute("SELECT id, nombre FROM marca_series WHERE marca_id=%s AND tipo_id=%s", (mid, tid))
                        for sid, sname in cur.fetchall():
                            cur.execute("SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, target_tid, sname))
                            ex = cur.fetchone()
                            if ex:
                                tsid = int(ex[0])
                                cur.execute("UPDATE model_hierarchy SET tipo_id=%s, serie_id=%s WHERE serie_id=%s", (target_tid, tsid, sid))
                                cur.execute("DELETE FROM marca_series WHERE id=%s", (sid,))
                                fused += 1
                            else:
                                cur.execute("UPDATE marca_series SET tipo_id=%s WHERE id=%s", (target_tid, sid))
                                cur.execute("UPDATE model_hierarchy SET tipo_id=%s WHERE serie_id=%s", (target_tid, sid))
                        # actualizar textual en models
                        cur.execute("UPDATE models SET tipo_equipo=%s WHERE marca_id=%s AND UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))", (fixed, mid, nombre))
                        # eliminar tipo viejo
                        cur.execute("DELETE FROM marca_tipos_equipo WHERE id=%s", (tid,))
                        renamed += 1
        conn.commit()
    print("renamed_types=", renamed, "fused_series=", fused)


if __name__ == '__main__':
    main()

