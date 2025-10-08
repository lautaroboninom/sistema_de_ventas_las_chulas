import os
import sys
import unicodedata
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


def simp(s: str) -> str:
    s2 = ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
    return ' '.join(s2.strip().upper().split())


def is_empty(v) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    if not s:
        return True
    return s.lower() in ('sin informacion', 'sin información', 'n/a', 'na', '-')


def score_customer(row) -> int:
    score = 0
    for k in ('cod_empresa','contacto','telefono','telefono_2','email'):
        if not is_empty(row.get(k)):
            score += 1
    # avoid choosing RELLENO unless only option
    if (row.get('razon_social') or '').strip().upper() == 'RELLENO':
        score -= 1
    return score


def dedupe_customers(conn) -> dict:
    merged = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id, razon_social, cod_empresa, contacto, telefono, telefono_2, email FROM customers")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
    # group by normalized razon_social
    groups = {}
    for r in data:
        key = simp(r['razon_social'] or '')
        groups.setdefault(key, []).append(r)
    with conn.transaction():
        with conn.cursor() as cur:
            for key, items in groups.items():
                if len(items) < 2:
                    continue
                # pick canonical with best score then lowest id
                items_sorted = sorted(items, key=lambda x: (-score_customer(x), x['id']))
                canonical = items_sorted[0]
                dupes = items_sorted[1:]
                cid = canonical['id']
                # fill missing fields on canonical from dupes
                update_sets = []
                update_vals = []
                for field in ('cod_empresa','contacto','telefono','telefono_2','email'):
                    if is_empty(canonical.get(field)):
                        for d in dupes:
                            if not is_empty(d.get(field)):
                                update_sets.append(f"{field}=%s")
                                update_vals.append(d.get(field))
                                canonical[field] = d.get(field)
                                break
                if update_sets:
                    update_vals.append(cid)
                    cur.execute(f"UPDATE customers SET {', '.join(update_sets)} WHERE id=%s", update_vals)
                # reassign FKs devices -> canonical customer
                for d in dupes:
                    cur.execute("UPDATE devices SET customer_id=%s WHERE customer_id=%s", (cid, d['id']))
                # delete duplicates
                for d in dupes:
                    cur.execute("DELETE FROM customers WHERE id=%s", (d['id'],))
                merged += len(dupes)
    return {'merged': merged}


def dedupe_users(conn) -> dict:
    merged = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id, email, nombre, rol, activo FROM users")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
    # by email first
    by_email = {}
    for r in data:
        email = (r['email'] or '').strip().lower()
        if not email:
            continue
        by_email.setdefault(email, []).append(r)
    targets = []
    for email, items in by_email.items():
        if len(items) > 1:
            items_sorted = sorted(items, key=lambda x: (0 if (x['email'] and 'local.invalid' not in x['email']) else 1, x['id']))
            canonical = items_sorted[0]
            dupes = items_sorted[1:]
            targets.append((canonical, dupes))
    # also by name where one is local.invalid
    by_name = {}
    for r in data:
        name = simp(r['nombre'] or '')
        by_name.setdefault(name, []).append(r)
    for name, items in by_name.items():
        # pick canonical: real email over local.invalid
        real = [x for x in items if x['email'] and 'local.invalid' not in (x['email'] or '')]
        fake = [x for x in items if x['email'] and 'local.invalid' in (x['email'] or '')]
        if real and fake:
            canonical = sorted(real, key=lambda x: x['id'])[0]
            targets.append((canonical, fake))
    # apply merges
    with conn.transaction():
        with conn.cursor() as cur:
            for canonical, dupes in targets:
                cid = canonical['id']
                ids = [d['id'] for d in dupes if d['id'] != cid]
                if not ids:
                    continue
                # reassign FKs
                cur.execute("UPDATE ingresos SET asignado_a=%s WHERE asignado_a = ANY(%s)", (cid, ids))
                cur.execute("UPDATE ingresos SET recibido_por=%s WHERE recibido_por = ANY(%s)", (cid, ids))
                cur.execute("UPDATE ingreso_events SET usuario_id=%s WHERE usuario_id = ANY(%s)", (cid, ids))
                cur.execute("UPDATE marcas SET tecnico_id=%s WHERE tecnico_id = ANY(%s)", (cid, ids))
                cur.execute("UPDATE models SET tecnico_id=%s WHERE tecnico_id = ANY(%s)", (cid, ids))
                # delete dupes
                for uid in ids:
                    cur.execute("DELETE FROM users WHERE id=%s", (uid,))
                merged += len(ids)
    return {'merged': merged}


def unify_types(conn) -> dict:
    # unify catalogo_tipos_equipo and marca_tipos_equipo by unaccented/global rules
    fixed = 0
    with conn.transaction():
        with conn.cursor() as cur:
            # 0) Global string fixes (common Spanish accents/typos)
            replacements = [
                ('OXIGENO', 'OXÍGENO'),
                ('BATERIAS', 'BATERÍAS'),
                ('BATERIA', 'BATERÍA'),
                ('BATERAS', 'BATERÍAS'),
                ('BATER�AS', 'BATERÍAS'),
            ]
            for src, dst in replacements:
                cur.execute("UPDATE marca_tipos_equipo SET nombre=REPLACE(nombre,%s,%s) WHERE POSITION(UPPER(%s) IN UPPER(nombre))>0", (src, dst, src))
                fixed += cur.rowcount or 0
            for src, dst in replacements:
                cur.execute("UPDATE models SET tipo_equipo=REPLACE(tipo_equipo,%s,%s) WHERE POSITION(UPPER(%s) IN UPPER(tipo_equipo))>0", (src, dst, src))
                fixed += cur.rowcount or 0

            # unify catalogo_tipos_equipo names to preferred accented variant where exists
            cur.execute("SELECT id, nombre FROM catalogo_tipos_equipo")
            cat = cur.fetchall()
            by_norm = {}
            for iid, nombre in cat:
                by_norm.setdefault(simp(nombre), []).append((iid, nombre))
            for norm, items in by_norm.items():
                if len(items) < 2:
                    continue
                # choose preferred with non-ascii chars if present else first
                def has_accent(s):
                    try:
                        s.encode('ascii')
                        return False
                    except Exception:
                        return True
                items_sorted = sorted(items, key=lambda x: (0 if has_accent(x[1]) else 1, x[1]))
                canonical_id, canonical_name = items_sorted[0]
                others = items_sorted[1:]
                for oid, oname in others:
                    # just delete duplicates; names same normalized. no FK here
                    cur.execute("DELETE FROM catalogo_tipos_equipo WHERE id=%s", (oid,))
                    fixed += 1

            # unify marca_tipos_equipo per marca_id, handling marca_series safely
            cur.execute("SELECT id, marca_id, nombre FROM marca_tipos_equipo")
            rows = cur.fetchall()
            by_marca = {}
            for iid, mid, nombre in rows:
                by_marca.setdefault(mid, []).append((iid, nombre))
            for mid, items in by_marca.items():
                groups = {}
                for iid, nombre in items:
                    groups.setdefault(simp(nombre), []).append((iid, nombre))
                for norm, gitems in groups.items():
                    if len(gitems) < 2:
                        continue
                    def has_accent(s):
                        try:
                            s.encode('ascii')
                            return False
                        except Exception:
                            return True
                    gsorted = sorted(gitems, key=lambda x: (0 if has_accent(x[1]) else 1, x[1]))
                    canonical_id, canonical_name = gsorted[0]
                    dup_ids = [d[0] for d in gsorted[1:]]
                    if not dup_ids:
                        continue
                    # handle marca_series rows under duplicate tipo_ids
                    cur.execute(
                        "SELECT id, tipo_id, nombre FROM marca_series WHERE marca_id=%s AND tipo_id = ANY(%s)",
                        (mid, dup_ids),
                    )
                    srows = cur.fetchall()
                    for sid, tipo_id, sname in srows:
                        # check if canonical series already exists for same name
                        cur.execute(
                            "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
                            (mid, canonical_id, sname),
                        )
                        exists = cur.fetchone()
                        if exists:
                            target_sid = exists[0]
                            # move model_hierarchy to target series
                            cur.execute("UPDATE model_hierarchy SET tipo_id=%s, serie_id=%s WHERE serie_id=%s",
                                        (canonical_id, target_sid, sid))
                            # delete duplicate series row
                            cur.execute("DELETE FROM marca_series WHERE id=%s", (sid,))
                            fixed += 1
                        else:
                            # safe update series tipo_id
                            cur.execute("UPDATE marca_series SET tipo_id=%s WHERE id=%s", (canonical_id, sid))
                            # reflect in model_hierarchy
                            cur.execute("UPDATE model_hierarchy SET tipo_id=%s WHERE serie_id=%s", (canonical_id, sid))
                    # update textual models.tipo_equipo for this brand, from any duplicate name to canonical
                    for _, dname in gsorted[1:]:
                        cur.execute(
                            "UPDATE models SET tipo_equipo=%s WHERE marca_id=%s AND UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))",
                            (canonical_name, mid, dname),
                        )
                    # delete duplicate tipo rows
                    for did in dup_ids:
                        cur.execute("DELETE FROM marca_tipos_equipo WHERE id=%s", (did,))
                        fixed += 1
    return {'fixed': fixed}


def main():
    conn = connect_pg()
    try:
        res_c = dedupe_customers(conn)
        res_u = dedupe_users(conn)
        res_t = unify_types(conn)
        print('Customers merged:', res_c['merged'])
        print('Users merged:', res_u['merged'])
        print('Types unified:', res_t['fixed'])
    finally:
        conn.close()


if __name__ == '__main__':
    main()
