import os
import psycopg


def env(name, default=None):
    return os.getenv(name, default)


def connect():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def is_empty(v):
    if v is None:
        return True
    s = str(v).strip()
    if not s:
        return True
    return s.lower() in ('sin informacion','sin información','n/a','na','-')


def step1_dedupe_customers_exact(conn):
    merged = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id, razon_social, cod_empresa, contacto, telefono, telefono_2, email FROM customers")
        rows = cur.fetchall()
        cols = [getattr(d, 'name', None) or d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
    from collections import defaultdict
    groups = defaultdict(list)
    for r in data:
        key = (r['razon_social'] or '').strip().upper()
        groups[key].append(r)
    with conn.transaction():
        with conn.cursor() as cur:
            for key, items in groups.items():
                if not key or len(items) < 2:
                    continue
                items_sorted = sorted(items, key=lambda x: x['id'])
                canonical = items_sorted[0]
                dupes = items_sorted[1:]
                cid = canonical['id']
                # fill empty fields
                sets = []
                vals = []
                for field in ('cod_empresa','contacto','telefono','telefono_2','email'):
                    if is_empty(canonical.get(field)):
                        for d in dupes:
                            if not is_empty(d.get(field)):
                                sets.append(f"{field}=%s"); vals.append(d.get(field))
                                canonical[field] = d.get(field)
                                break
                if sets:
                    vals.append(cid)
                    cur.execute(f"UPDATE customers SET {', '.join(sets)} WHERE id=%s", vals)
                # reassign FKs
                for d in dupes:
                    cur.execute("UPDATE devices SET customer_id=%s WHERE customer_id=%s", (cid, d['id']))
                for d in dupes:
                    cur.execute("DELETE FROM customers WHERE id=%s", (d['id'],))
                    merged += 1
    return merged


def step2_users_lower_email(conn):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email=LOWER(email) WHERE email IS NOT NULL AND email <> LOWER(email)")
            return cur.rowcount


def step3_devices_clean_serial(conn):
    placeholders = ('s/n','sn','n/a','na','sin serial','no aplica','no aplica','s\n','--')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE devices
                   SET numero_serie = NULL
                 WHERE numero_serie IS NOT NULL
                   AND (
                        TRIM(numero_serie)='' OR
                        LOWER(TRIM(numero_serie)) = ANY(%s)
                       )
            """, (list(placeholders),))
            return cur.rowcount


def step4_recalc_full_name(conn):
    updated = 0
    with conn.cursor() as cur:
        cur.execute("""
            SELECT mh.model_id, mt.nombre AS tipo, ms.nombre AS serie, COALESCE(mv.nombre, '') AS variante,
                   mh.full_name
              FROM model_hierarchy mh
              JOIN marca_tipos_equipo mt ON mt.id = mh.tipo_id
              JOIN marca_series ms ON ms.id = mh.serie_id
         LEFT JOIN marca_series_variantes mv ON mv.id = mh.variante_id
        """)
        rows = cur.fetchall()
    with conn.transaction():
        with conn.cursor() as ucur:
            for model_id, tipo, serie, variante, full in rows:
                new_full = f"{(tipo or '').strip()} | {(serie or '').strip()}" + (f" {variante.strip()}" if variantestrip(variante) else '')
                if new_full != full:
                    ucur.execute("UPDATE model_hierarchy SET full_name=%s WHERE model_id=%s", (new_full, model_id))
                    updated += 1
    return updated


def variantestrip(v):
    if v is None:
        return ''
    return v.strip()


def main():
    conn = connect()
    try:
        m = step1_dedupe_customers_exact(conn)
        n = step2_users_lower_email(conn)
        d = step3_devices_clean_serial(conn)
        f = step4_recalc_full_name(conn)
        print('Customers merged (exact):', m)
        print('User emails lowercased:', n)
        print('Devices serials cleaned:', d)
        print('model_hierarchy full_name updated:', f)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
