import os
import csv
from typing import Dict, Any, Tuple

import pymysql  # type: ignore
import psycopg  # type: ignore


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


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


def connect_pg():
    host = env('PG_HOST', env('POSTGRES_HOST', 'localhost'))
    port = int(env('PG_PORT', env('POSTGRES_PORT', '5433')))
    db = env('PG_DB', env('POSTGRES_DB', 'servicio_tecnico'))
    user = env('PG_USER', env('POSTGRES_USER', 'sepid'))
    pw = env('PG_PASSWORD', env('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def simp(s: str) -> str:
    s = (s or '').strip().lower()
    return ' '.join(s.split())


def main():
    out_csv = os.path.join('outputs', 'tecnicos_asignados_diff.csv')
    os.makedirs('outputs', exist_ok=True)

    my = connect_mysql()
    pg = connect_pg()
    try:
        # MySQL: map users
        with my.cursor() as cur:
            cur.execute("SELECT id, nombre, email FROM users")
            my_users: Dict[int, Tuple[str,str]] = {int(r['id']): ((r['nombre'] or '').strip(), (r['email'] or '').strip()) for r in cur.fetchall()}  # type: ignore[index]
        # MySQL: asignaciones
        with my.cursor() as cur:
            cur.execute("SELECT id AS ingreso_id, asignado_a FROM ingresos")
            my_asg: Dict[int, int] = {}
            for r in cur.fetchall():  # type: ignore[assignment]
                try:
                    iid = int(r['ingreso_id'])
                except Exception:
                    continue
                uid = r['asignado_a']
                if uid is None:
                    continue
                try:
                    my_asg[iid] = int(uid)
                except Exception:
                    continue

        # PG: asignaciones + user info
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT i.id AS ingreso_id, i.asignado_a AS pg_user_id, COALESCE(u.nombre,''), COALESCE(u.email,'')
                FROM ingresos i LEFT JOIN users u ON u.id=i.asignado_a
                """
            )
            pg_asg: Dict[int, Tuple[int, str, str]] = {}
            for (iid, uid, name, email) in cur.fetchall():
                pg_asg[int(iid)] = (int(uid) if uid is not None else None, str(name or ''), str(email or ''))  # type: ignore[assignment]

        both_ids = set(my_asg.keys()).intersection(pg_asg.keys())
        missing_in_pg = [iid for iid in my_asg.keys() if iid not in pg_asg]
        missing_in_my = [iid for iid in pg_asg.keys() if iid not in my_asg]

        same = 0
        diff = 0
        only_my = 0
        only_pg = 0
        rows = []

        for iid in both_ids:
            my_uid = my_asg.get(iid)
            pg_uid, pg_name, pg_email = pg_asg.get(iid, (None, '', ''))
            my_name, my_email = my_users.get(my_uid, ('','')) if my_uid is not None else ('','')

            # criterio de igualdad: email o nombre normalizado
            eq = False
            if my_uid is None and pg_uid is None:
                eq = True
            if my_email and pg_email and simp(my_email) == simp(pg_email):
                eq = True
            if (not eq) and my_name and pg_name and simp(my_name) == simp(pg_name):
                eq = True
            if (not eq) and (my_uid is not None and pg_uid is not None and my_uid == pg_uid):
                eq = True

            if eq:
                same += 1
                status = 'ok'
            else:
                diff += 1
                status = 'diff'
            rows.append([iid, my_uid, my_name, my_email, pg_uid, pg_name, pg_email, status])

        for iid in missing_in_pg:
            only_my += 1
            my_uid = my_asg.get(iid)
            my_name, my_email = my_users.get(my_uid, ('','')) if my_uid is not None else ('','')
            rows.append([iid, my_uid, my_name, my_email, None, '', '', 'missing_pg'])
        for iid in missing_in_my:
            only_pg += 1
            pg_uid, pg_name, pg_email = pg_asg.get(iid, (None, '', ''))
            rows.append([iid, None, '', '', pg_uid, pg_name, pg_email, 'missing_mysql'])

        with open(out_csv, 'w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['ingreso_id','mysql_user_id','mysql_nombre','mysql_email','pg_user_id','pg_nombre','pg_email','status'])
            for r in rows:
                cw.writerow(r)

        print('Comparación completada')
        print('Ingresos en ambos:', len(both_ids))
        print('Coinciden:', same)
        print('Difieren:', diff)
        print('Solo en MySQL:', only_my)
        print('Solo en PG:', only_pg)
        print('CSV:', out_csv)
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

