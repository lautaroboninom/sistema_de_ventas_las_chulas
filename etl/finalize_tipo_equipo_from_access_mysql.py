"""
Completa/corrige models.tipo_equipo en Postgres para todos los modelos usados por OS (ingresos),
usando Access como fuente principal (Servicio.IdEquipo -> Equipos.Equipo) y como fallback
el tipo de MySQL (join por marca+modelo).

Reglas:
- Preferir Access cuando hay dato. Si no hay, usar MySQL si coincide por marca+modelo.
- Actualiza models.tipo_equipo cuando está vacío o distinto del valor deducido (preferencia Access).

Salida: outputs/finalize_tipo_equipo_report.csv
"""

from __future__ import annotations

import csv
import os
from typing import Dict, Optional, Tuple

import psycopg  # type: ignore
import pymysql  # type: ignore

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_pg():
    host = env('PG_HOST', env('POSTGRES_HOST', 'localhost'))
    port = int(env('PG_PORT', env('POSTGRES_PORT', '5433')))
    db = env('PG_DB', env('POSTGRES_DB', 'servicio_tecnico'))
    user = env('PG_USER', env('POSTGRES_USER', 'sepid'))
    pw = env('PG_PASSWORD', env('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def connect_mysql():
    return pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306") or 3306),
        user=env("MYSQL_USER", "sepid"),
        password=env("MYSQL_PASSWORD", "supersegura"),
        database=env("MYSQL_DATABASE", env("MYSQL_DB", "servicio_tecnico")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def connect_access():
    assert pyodbc is not None, "pyodbc no disponible para Access"
    db_path = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={db_path};", autocommit=True)


def build_mysql_tipo_index(my) -> Dict[Tuple[str, str], str]:
    """Mapa (marca_lower, modelo_lower) -> tipo_equipo (MySQL)"""
    idx: Dict[Tuple[str, str], str] = {}
    with my.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(b.nombre,'' ) AS marca, COALESCE(m.nombre,'') AS modelo, COALESCE(m.tipo_equipo,'') AS tipo
            FROM models m LEFT JOIN marcas b ON b.id=m.marca_id
            WHERE m.tipo_equipo IS NOT NULL AND TRIM(m.tipo_equipo)<>''
            """
        )
        for r in cur.fetchall():
            mk = (str(r['marca'] or '').strip().lower(), str(r['modelo'] or '').strip().lower())
            te = (r['tipo'] or '').strip()
            if mk[0] and mk[1] and te:
                idx[mk] = te
    return idx


def main():
    out_csv = os.path.join('outputs', 'finalize_tipo_equipo_report.csv')
    os.makedirs('outputs', exist_ok=True)

    pg = connect_pg()
    my = connect_mysql()
    acc = None
    try:
        try:
            acc = connect_access() if pyodbc is not None else None
        except Exception:
            acc = None

        mysql_tipo = build_mysql_tipo_index(my)
        acc_cur = acc.cursor() if acc is not None else None

        # Traer todos los ingresos con su device y model
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT i.id AS os_id, d.id AS device_id, m.id AS model_id,
                       COALESCE(b.nombre,'' ) AS marca, COALESCE(m.nombre,'') AS modelo,
                       COALESCE(m.tipo_equipo,'') AS tipo_pg
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN marcas b ON b.id=m.marca_id
                ORDER BY i.id ASC
                """
            )
            rows = cur.fetchall()

        # Propuestas por model_id
        proposed: Dict[int, Tuple[str, str]] = {}  # model_id -> (tipo, source)
        conflicts: Dict[int, Dict[str, int]] = {}

        for (os_id, device_id, model_id, marca, modelo, tipo_pg) in rows:
            if model_id is None:
                continue
            tipo_src: Optional[str] = None
            source = ''
            # 1) Access
            if acc_cur is not None:
                try:
                    acc_cur.execute("SELECT IdEquipo FROM [Servicio] WHERE Id=?", (int(os_id),))
                    a = acc_cur.fetchone()
                except Exception:
                    a = None
                ideq = a[0] if a else None
                if ideq is not None:
                    try:
                        acc_cur.execute("SELECT Equipo FROM [Equipos] WHERE IdEquipos=?", (ideq,))
                        b = acc_cur.fetchone()
                        equipo = (b[0] or '').strip() if b else ''
                    except Exception:
                        equipo = ''
                    if equipo:
                        tipo_src = equipo
                        source = 'access'
            # 2) Fallback MySQL by brand+model
            if not tipo_src:
                key = (str(marca or '').strip().lower(), str(modelo or '').strip().lower())
                tipo_src = mysql_tipo.get(key)
                if tipo_src:
                    source = 'mysql'

            if not tipo_src:
                continue

            # Registrar propuesta por model
            if model_id not in proposed:
                proposed[model_id] = (tipo_src, source)
            else:
                # Conflicto: registrar frecuencia
                prev_tipo, prev_src = proposed[model_id]
                if prev_tipo != tipo_src:
                    freq = conflicts.setdefault(model_id, {})
                    freq[prev_tipo] = freq.get(prev_tipo, 0) + 1
                    freq[tipo_src] = freq.get(tipo_src, 0) + 1
                    # Preferir access
                    if source == 'access' and prev_src != 'access':
                        proposed[model_id] = (tipo_src, source)

        updated = 0
        unchanged = 0
        mismatched = 0
        with pg.transaction():
            with pg.cursor() as cur:
                for (model_id, (tipo, src)) in proposed.items():
                    cur.execute("SELECT COALESCE(tipo_equipo,'') FROM models WHERE id=%s", (model_id,))
                    cur_tipo = (cur.fetchone() or [''])[0] or ''
                    if not cur_tipo:
                        cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, model_id))
                        updated += 1
                    elif str(cur_tipo).strip() != str(tipo).strip():
                        # corregir si nuestra fuente es access; si proviene de mysql pero PG ya tenia valor, solo marcar mismatched
                        if src == 'access':
                            cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, model_id))
                            updated += 1
                        else:
                            mismatched += 1
                    else:
                        unchanged += 1
        pg.commit()

        # Reporte
        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['model_id','tipo_final','source','estado'])
            for mid, (tipo, src) in proposed.items():
                cw.writerow([mid, tipo, src, 'aplicado'])
        print('Finalize tipo_equipo:')
        print('Modelos con propuesta:', len(proposed))
        print('Actualizados:', updated)
        print('Sin cambio:', unchanged)
        print('Conflictos (mismatched mantenidos):', mismatched)
        print('CSV:', out_csv)

    finally:
        try:
            pg.close()
        except Exception:
            pass
        try:
            my.close()
        except Exception:
            pass
        try:
            if acc is not None:
                acc.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

