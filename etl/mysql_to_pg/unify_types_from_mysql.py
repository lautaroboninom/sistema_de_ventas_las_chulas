"""
Unifica los tipos de equipo en PostgreSQL usando como referencia los nombres de MySQL.

Para cada marca (marca_id):
 - Agrupa tipos por nombre normalizado (sin tildes, mayúsculas)
 - Toma como canónico el nombre que aparece en MySQL para ese normalizado
   (si no existe en MySQL, usa el primero con tildes si hay; si no, el primero alfabético)
 - Garantiza que exista un tipo con el nombre canónico en esa marca
 - Migra todas las series (marca_series) de los tipos no canónicos al canónico,
   fusionando series que colisionen por nombre (y reubicando model_hierarchy)
 - Actualiza models.tipo_equipo textual de los nombres viejos al canónico
 - Elimina los tipos no canónicos

Evita violaciones de UNIQUE (marca_id,nombre) realizando merges de series antes de borrar/renombrar.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Dict, List, Tuple, Optional

import pymysql  # type: ignore
import psycopg


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def simp(s: str) -> str:
    s2 = ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
    return ' '.join(s2.strip().upper().split())


def has_accent(s: str) -> bool:
    try:
        s.encode('ascii')
        return False
    except Exception:
        return True


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


def build_canonical_map_from_mysql(my) -> Dict[str, str]:
    """Devuelve norm -> nombre canónico según MySQL (prefiere tildes)."""
    with my.cursor() as cur:
        cur.execute("SELECT DISTINCT nombre FROM marca_tipos_equipo")
        names = [r["nombre"] for r in cur.fetchall()]
    groups: Dict[str, List[str]] = {}
    for n in names:
        groups.setdefault(simp(n), []).append(n)
    out: Dict[str, str] = {}
    for k, arr in groups.items():
        # preferir con tildes, luego orden alfabético
        arr_sorted = sorted(arr, key=lambda s: (0 if has_accent(s) else 1, s))
        canon = arr_sorted[0]
        # Forzar acentos en tokens comunes
        fixes = {
            'OXIGENO': 'OXÍGENO',
            'BATERIAS': 'BATERÍAS',
            'BATERIA': 'BATERÍA',
            'BATERAS': 'BATERÍAS',
            'PORTATIL': 'PORTÁTIL',
        }
        uc = canon.upper()
        for src, dst in fixes.items():
            if src in uc:
                # reemplazo conservando mayúsculas
                uc = uc.replace(src, dst)
        canon = uc  # mantener todo mayúsculas (coincide con tus listas)
        out[k] = canon
    return out


def main():
    my = connect_mysql()
    pg = connect_pg()
    try:
        canonical = build_canonical_map_from_mysql(my)
        fixed_types = 0
        fused_series = 0
        with pg.transaction():
            with pg.cursor() as cur:
                # por marca
                cur.execute("SELECT DISTINCT marca_id FROM marca_tipos_equipo ORDER BY marca_id")
                marca_ids = [r[0] for r in cur.fetchall()]
                for mid in marca_ids:
                    cur.execute("SELECT id, nombre FROM marca_tipos_equipo WHERE marca_id=%s ORDER BY id", (mid,))
                    types = cur.fetchall()
                    groups: Dict[str, List[Tuple[int, str]]] = {}
                    for tid, nombre in types:
                        groups.setdefault(simp(nombre), []).append((int(tid), str(nombre)))
                    for norm, items in groups.items():
                        if len(items) < 2:
                            # si el único nombre no coincide con canonical, renombrar seguro
                            canonical_name = canonical.get(norm)
                            if canonical_name and items:
                                tid, name = items[0]
                                if name != canonical_name:
                                    # renombrar si no genera colisión
                                    cur.execute("SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, canonical_name))
                                    row = cur.fetchone()
                                    if row:
                                        # existe otro id con canonical: migrar series
                                        canonical_id = int(row[0])
                                        # migrar series de tid -> canonical_id
                                        cur.execute("SELECT id, nombre FROM marca_series WHERE marca_id=%s AND tipo_id=%s", (mid, tid))
                                        for sid, sname in cur.fetchall():
                                            cur.execute("SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, canonical_id, sname))
                                            ex = cur.fetchone()
                                            if ex:
                                                target_sid = int(ex[0])
                                                cur.execute("UPDATE model_hierarchy SET tipo_id=%s, serie_id=%s WHERE serie_id=%s", (canonical_id, target_sid, sid))
                                                cur.execute("DELETE FROM marca_series WHERE id=%s", (sid,))
                                                fused_series += 1
                                            else:
                                                cur.execute("UPDATE marca_series SET tipo_id=%s WHERE id=%s", (canonical_id, sid))
                                                cur.execute("UPDATE model_hierarchy SET tipo_id=%s WHERE serie_id=%s", (canonical_id, sid))
                                        cur.execute("DELETE FROM marca_tipos_equipo WHERE id=%s", (tid,))
                                        fixed_types += 1
                                    else:
                                        # renombrar directamente
                                        cur.execute("UPDATE marca_tipos_equipo SET nombre=%s WHERE id=%s", (canonical_name, tid))
                                        fixed_types += 1
                            continue

                        # hay duplicados para este normalizado: escoger canonical global
                        canonical_name = canonical.get(norm)
                        # si no hay en MySQL, escoger con tildes o el primero
                        if not canonical_name:
                            items_sorted = sorted(items, key=lambda x: (0 if has_accent(x[1]) else 1, x[1]))
                            # aplicar fixes de tokens al nombre elegido
                            sample_name = items_sorted[0][1].upper()
                            for src, dst in {
                                'OXIGENO':'OXÍGENO', 'BATERIAS':'BATERÍAS', 'BATERIA':'BATERÍA', 'BATERAS':'BATERÍAS', 'PORTATIL':'PORTÁTIL'
                            }.items():
                                if src in sample_name:
                                    sample_name = sample_name.replace(src, dst)
                            canonical_name = sample_name
                            canonical_id = None
                            # canonical_id ya es int, pero para flujos siguientes queremos el nombre
                        # asegurar canonical_id para este nombre en esta marca
                        cur.execute("SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, canonical_name))
                        row = cur.fetchone()
                        if row:
                            canonical_id = int(row[0])
                        else:
                            # crear canonical y usarlo como target
                            cur.execute("INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE) RETURNING id", (mid, canonical_name))
                            canonical_id = int(cur.fetchone()[0])
                            fixed_types += 1
                        # migrar todos los demás tipos al canonical
                        for tid, name in items:
                            if tid == canonical_id:
                                continue
                            # migrar series del tid -> canonical_id
                            cur.execute("SELECT id, nombre FROM marca_series WHERE marca_id=%s AND tipo_id=%s", (mid, tid))
                            for sid, sname in cur.fetchall():
                                cur.execute("SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (mid, canonical_id, sname))
                                ex = cur.fetchone()
                                if ex:
                                    target_sid = int(ex[0])
                                    cur.execute("UPDATE model_hierarchy SET tipo_id=%s, serie_id=%s WHERE serie_id=%s", (canonical_id, target_sid, sid))
                                    cur.execute("DELETE FROM marca_series WHERE id=%s", (sid,))
                                    fused_series += 1
                                else:
                                    cur.execute("UPDATE marca_series SET tipo_id=%s WHERE id=%s", (canonical_id, sid))
                                    cur.execute("UPDATE model_hierarchy SET tipo_id=%s WHERE serie_id=%s", (canonical_id, sid))
                            # actualizar models.tipo_equipo textual
                            cur.execute("UPDATE models SET tipo_equipo=%s WHERE marca_id=%s AND UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))", (canonical_name, mid, name))
                            # borrar tipo viejo
                            cur.execute("DELETE FROM marca_tipos_equipo WHERE id=%s", (tid,))
                            fixed_types += 1
        pg.commit()
        print("fixed_types=", fixed_types, "fused_series=", fused_series)
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
