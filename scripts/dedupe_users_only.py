import os
import psycopg


def env(name, default=None):
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
    merged = 0
    with connect_pg() as conn:
        # fetch users
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, email FROM users")
            rows = cur.fetchall()
            cols = [getattr(d, 'name', None) or d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]

        # group by name (normalized)
        from collections import defaultdict
        groups = defaultdict(list)
        for r in data:
            name = (r.get('nombre') or '').strip().upper()
            groups[name].append(r)

        with conn.transaction():
            with conn.cursor() as cur:
                for name, users in groups.items():
                    if len(users) < 2:
                        continue
                    # separate real vs local.invalid mails
                    real = [u for u in users if u.get('email') and 'local.invalid' not in (u.get('email') or '')]
                    fake = [u for u in users if u.get('email') and 'local.invalid' in (u.get('email') or '')]
                    keep = None
                    dup_ids = []
                    if real:
                        keep = sorted(real, key=lambda x: x['id'])[0]
                        dup_ids = [u['id'] for u in users if u['id'] != keep['id']]
                    else:
                        # no real, keep lowest id
                        keep = sorted(users, key=lambda x: x['id'])[0]
                        dup_ids = [u['id'] for u in users if u['id'] != keep['id']]
                    if not dup_ids:
                        continue
                    # reassign FKs
                    cur.execute("UPDATE ingresos SET asignado_a=%s WHERE asignado_a = ANY(%s)", (keep['id'], dup_ids))
                    cur.execute("UPDATE ingresos SET recibido_por=%s WHERE recibido_por = ANY(%s)", (keep['id'], dup_ids))
                    cur.execute("UPDATE ingreso_events SET usuario_id=%s WHERE usuario_id = ANY(%s)", (keep['id'], dup_ids))
                    cur.execute("UPDATE marcas SET tecnico_id=%s WHERE tecnico_id = ANY(%s)", (keep['id'], dup_ids))
                    cur.execute("UPDATE models SET tecnico_id=%s WHERE tecnico_id = ANY(%s)", (keep['id'], dup_ids))
                    # delete dupes
                    for uid in dup_ids:
                        cur.execute("DELETE FROM users WHERE id=%s", (uid,))
                        merged += 1
        conn.commit()
    print("Users merged:", merged)


if __name__ == '__main__':
    main()

