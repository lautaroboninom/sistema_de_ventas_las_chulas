#!/usr/bin/env python
import argparse
import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import psycopg2


@dataclass
class DbItem:
    id: int
    codigo: str
    nombre: str
    activo: bool
    norm: str
    tokens: set[str]
    has_magnamed: bool


def load_env_file(path: Path) -> None:
    if not path or not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def connect_db(host_override: str | None = None):
    host = host_override or os.getenv("POSTGRES_HOST", "localhost")
    if host == "postgres":
        host = "localhost"
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=host,
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


_NON_ALNUM = re.compile(r"[^A-Z0-9]+")

TOKEN_MAP = {
    "BRAZO": "ARM",
    "ARTICULADO": "ARTICULATED",
    "CIRCUITO": "CIRCUIT",
    "RESPIRATORIO": "RESPIRATORY",
    "PACIENTE": "PATIENT",
    "VALVULA": "VALVE",
    "VALVULLA": "VALVE",
    "DIAFRAGMA": "DIAPHRAGM",
    "DIFRAGMA": "DIAPHRAGM",
    "FILTRO": "FILTER",
    "MANGUERA": "HOSE",
    "PROLONGADOR": "EXTENSION",
    "MASCARA": "MASK",
    "ADULTO": "ADULT",
    "PEDIATRICO": "PEDIATRIC",
    "PEDIATRICA": "PEDIATRIC",
    "O2": "OXYGEN",
    "OXIGENO": "OXYGEN",
    "AGUA": "WATER",
    "TRAMPA": "TRAP",
    "TEMPERATURA": "TEMP",
    "CALENTADOR": "HEATER",
    "CALENTADO": "HEATED",
    "HUMIDIFICADOR": "HUMIDIFIER",
    "HUMIDIFICATION": "HUMIDIFIER",
    "NEBULIZADOR": "NEBULIZER",
    "ADAPTADOR": "ADAPTER",
    "CONECTOR": "CONNECTOR",
    "CONEXION": "CONNECTION",
    "CANULA": "CANNULA",
    "SILICONA": "SILICONE",
    "FLUJO": "FLOW",
    "PRESION": "PRESSURE",
}


def normalize_name(name: str, drop_brand: bool = True) -> str:
    if not name:
        return ""
    txt = unicodedata.normalize("NFKD", name)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = txt.upper()
    txt = _NON_ALNUM.sub(" ", txt)
    tokens = txt.split()
    # Drop brand token to avoid biasing similarity
    if drop_brand:
        tokens = [t for t in tokens if t != "MAGNAMED"]
    mapped = [TOKEN_MAP.get(t, t) for t in tokens]
    return " ".join(mapped)


def token_overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return (2.0 * inter) / (len(a) + len(b))


def similarity(a: str, b: str, tokens_a: set[str], tokens_b: set[str]) -> float:
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    tok = token_overlap(tokens_a, tokens_b)
    return max(seq, tok)


def load_magnamed_csv(path: Path):
    items = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            codigo = (row.get("codigo") or "").strip()
            nombre = (row.get("nombre") or "").strip()
            costo = (row.get("costo_usd") or "").strip()
            if not nombre:
                continue
            norm = normalize_name(nombre)
            tokens = set(norm.split())
            items.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "costo_usd": costo,
                    "norm": norm,
                    "tokens": tokens,
                }
            )
    return items


def load_db_items(conn) -> list[DbItem]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, codigo, nombre, activo FROM catalogo_repuestos")
        rows = cur.fetchall() or []
    items: list[DbItem] = []
    for rid, codigo, nombre, activo in rows:
        nombre = nombre or ""
        norm = normalize_name(nombre)
        tokens = set(norm.split())
        has_magnamed = "MAGNAMED" in normalize_name(nombre, drop_brand=False).split()
        items.append(
            DbItem(
                id=rid,
                codigo=str(codigo),
                nombre=nombre,
                activo=bool(activo),
                norm=norm,
                tokens=tokens,
                has_magnamed=has_magnamed,
            )
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Match Magnamed price list items to catalogo_repuestos by name")
    parser.add_argument("--csv", required=True, help="Magnamed CSV (from import script)")
    parser.add_argument("--env", default=".env.prod", help="Path to .env file (default: .env.prod)")
    parser.add_argument("--host", default=None, help="Override DB host (default: from env)")
    parser.add_argument("--top", type=int, default=3, help="Top matches per item (default: 3)")
    parser.add_argument("--threshold", type=float, default=0.60, help="Threshold for magnamed-only list (default: 0.60)")
    parser.add_argument("--out-top", default="etl/out/magnamed_name_matches_top3.csv", help="Output CSV for top matches")
    parser.add_argument(
        "--out-magnamed",
        default="etl/out/magnamed_db_magnamed_matches.csv",
        help="Output CSV for matches where DB name contains MAGNAMED",
    )
    parser.add_argument(
        "--out-db-magnamed",
        default="etl/out/db_magnamed_to_list_matches.csv",
        help="Output CSV for DB names containing MAGNAMED matched to list items",
    )
    parser.add_argument("--db-top", type=int, default=3, help="Top matches per DB MAGNAMED item (default: 3)")
    args = parser.parse_args()

    env_path = Path(args.env) if args.env else None
    if env_path:
        load_env_file(env_path)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    try:
        conn = connect_db(args.host)
    except Exception as e:
        print(f"DB connection failed: {e}")
        return 2

    try:
        magnamed = load_magnamed_csv(csv_path)
        db_items = load_db_items(conn)
    finally:
        conn.close()

    out_top = Path(args.out_top)
    out_top.parent.mkdir(parents=True, exist_ok=True)
    out_mag = Path(args.out_magnamed)
    out_mag.parent.mkdir(parents=True, exist_ok=True)
    out_db_mag = Path(args.out_db_magnamed)
    out_db_mag.parent.mkdir(parents=True, exist_ok=True)

    magnamed_matches = 0
    with out_top.open("w", newline="", encoding="utf-8") as f_top, out_mag.open(
        "w", newline="", encoding="utf-8"
    ) as f_mag, out_db_mag.open("w", newline="", encoding="utf-8") as f_db:
        w_top = csv.writer(f_top)
        w_mag = csv.writer(f_mag)
        w_db = csv.writer(f_db)
        w_top.writerow(
            [
                "magnamed_codigo",
                "magnamed_nombre",
                "costo_usd",
                "rank",
                "match_codigo",
                "match_nombre",
                "match_activo",
                "score",
                "match_has_magnamed",
            ]
        )
        w_mag.writerow(
            [
                "magnamed_codigo",
                "magnamed_nombre",
                "costo_usd",
                "match_codigo",
                "match_nombre",
                "match_activo",
                "score",
            ]
        )
        w_db.writerow(
            [
                "db_codigo",
                "db_nombre",
                "db_activo",
                "match_magnamed_codigo",
                "match_magnamed_nombre",
                "costo_usd",
                "score",
            ]
        )

        for item in magnamed:
            scores = []
            for db in db_items:
                s = similarity(item["norm"], db.norm, item["tokens"], db.tokens)
                if s == 0:
                    continue
                scores.append((s, db))
            scores.sort(key=lambda x: x[0], reverse=True)
            top = scores[: max(1, args.top)]
            for rank, (s, db) in enumerate(top, 1):
                w_top.writerow(
                    [
                        item["codigo"],
                        item["nombre"],
                        item["costo_usd"],
                        rank,
                        db.codigo,
                        db.nombre,
                        "1" if db.activo else "0",
                        f"{s:.3f}",
                        "1" if db.has_magnamed else "0",
                    ]
                )
            if top:
                best_s, best_db = top[0]
                if best_db.has_magnamed and best_s >= args.threshold:
                    w_mag.writerow(
                        [
                            item["codigo"],
                            item["nombre"],
                            item["costo_usd"],
                            best_db.codigo,
                            best_db.nombre,
                            "1" if best_db.activo else "0",
                            f"{best_s:.3f}",
                        ]
                    )
                    magnamed_matches += 1

        # Reverse: for DB items containing MAGNAMED, find best list matches
        db_magnamed = [d for d in db_items if d.has_magnamed]
        for db in db_magnamed:
            scores = []
            for item in magnamed:
                s = similarity(item["norm"], db.norm, item["tokens"], db.tokens)
                if s == 0:
                    continue
                scores.append((s, item))
            scores.sort(key=lambda x: x[0], reverse=True)
            for s, item in scores[: max(1, args.db_top)]:
                w_db.writerow(
                    [
                        db.codigo,
                        db.nombre,
                        "1" if db.activo else "0",
                        item["codigo"],
                        item["nombre"],
                        item["costo_usd"],
                        f"{s:.3f}",
                    ]
                )

    print(f"Magnamed items: {len(magnamed)}")
    print(f"Top matches written: {out_top}")
    print(f"Magnamed-name matches (>= {args.threshold}): {magnamed_matches} -> {out_mag}")
    print(f"DB MAGNAMED matches written: {out_db_mag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
