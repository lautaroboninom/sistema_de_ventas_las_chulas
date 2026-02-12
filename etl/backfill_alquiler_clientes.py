from __future__ import annotations

import csv
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from difflib import SequenceMatcher

import psycopg  # type: ignore

OUT_DIR = Path('etl/out')
OUT_MATCHED = OUT_DIR / 'alquiler_clientes_exact_updates.csv'
OUT_CANDIDATES = OUT_DIR / 'alquiler_clientes_no_exact_match.csv'
ENV_FILE = Path('.env')
DRY_RUN = os.getenv('DRY_RUN', '').strip().lower() in ('1','true','yes')


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            s = line.strip()
            if not s or s.startswith('#') or '=' not in s:
                continue
            k, v = s.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return


def connect_pg():
    load_env_file(ENV_FILE)
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def norm_key_exact(s: str) -> str:
    return (s or '').strip().upper()


def norm_soft(s: str) -> str:
    s = (s or '').strip().lower()
    if not s:
        return ''
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def best_candidate(name_norm: str, customers):
    best = (None, 0.0)
    for cid, rs, rs_norm in customers:
        if not rs_norm:
            continue
        score = SequenceMatcher(None, name_norm, rs_norm).ratio()
        if score > best[1]:
            best = ((cid, rs), score)
    return best


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT id, razon_social FROM customers")
            customers = [(int(r[0]), (r[1] or '').strip(), norm_soft(r[1] or '')) for r in cur.fetchall()]
            by_exact = {}
            for cid, rs, _ in customers:
                key = norm_key_exact(rs)
                if not key:
                    continue
                if key not in by_exact or cid < by_exact[key][0]:
                    by_exact[key] = (cid, rs)

            cur.execute(
                """
                SELECT t.id AS ingreso_id, t.device_id, t.alquiler_a
                FROM ingresos t
                WHERE COALESCE(t.alquilado,false)=true
                  AND t.alquiler_a IS NOT NULL
                  AND TRIM(t.alquiler_a) <> ''
                """
            )
            rows = cur.fetchall()

            exact_updates = []
            unmatched = defaultdict(lambda: {"ingresos": set(), "devices": set()})

            for ingreso_id, device_id, alquiler_a in rows:
                name = (alquiler_a or '').strip()
                key = norm_key_exact(name)
                if key in by_exact:
                    cid, rs = by_exact[key]
                    cur.execute("SELECT customer_id FROM devices WHERE id=%s", (device_id,))
                    row = cur.fetchone()
                    current_cid = int(row[0]) if row and row[0] is not None else None
                    if current_cid != cid:
                        if not DRY_RUN:
                            cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (cid, device_id))
                        exact_updates.append((ingreso_id, device_id, name, cid, rs, current_cid))
                else:
                    bucket = unmatched[name]
                    bucket["ingresos"].add(int(ingreso_id))
                    bucket["devices"].add(int(device_id))
        if not DRY_RUN:
            cn.commit()

    with OUT_MATCHED.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(["ingreso_id","device_id","alquiler_a","customer_id","customer_rs","customer_id_prev"])
        for r in exact_updates:
            w.writerow(r)

    with OUT_CANDIDATES.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(["alquiler_a","best_customer_id","best_customer_rs","score","ingreso_ids","device_ids"])
        for raw_name, meta in sorted(unmatched.items(), key=lambda x: x[0].lower()):
            nsoft = norm_soft(raw_name)
            (best, score) = best_candidate(nsoft, customers)
            if best:
                cid, rs = best
            else:
                cid, rs = (None, '')
            w.writerow([
                raw_name,
                cid,
                rs,
                f"{score:.3f}" if best else "",
                ",".join(str(x) for x in sorted(meta["ingresos"])),
                ",".join(str(x) for x in sorted(meta["devices"])),
            ])

    if DRY_RUN:
        print('DRY_RUN=1 (no updates applied)')
    print(f"Exact updates: {len(exact_updates)} -> {OUT_MATCHED}")
    print(f"No exact match: {len(unmatched)} -> {OUT_CANDIDATES}")


if __name__ == '__main__':
    main()
