import json
import math
import os
import re
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

REPO_ROOT = Path(r"Z:/Servicio Tecnico/1_SISTEMA REPARACIONES/Nuevo Sistema de reparación")
OUTPUT_DIR = REPO_ROOT / "outputs"
TMP_DIR = REPO_ROOT / "tmp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

DB_CFG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "mysqlroot",
    "database": "servicio_tecnico",
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
})

CACHE_FILE = TMP_DIR / "source_cache.json"
if CACHE_FILE.exists():
    try:
        SOURCE_CACHE = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        SOURCE_CACHE = {}
else:
    SOURCE_CACHE = {}

HIGH = 92.0
MED = 85.0

STOP_DOMAINS = {"duckduckgo.com", "www.duckduckgo.com", "bing.com", "www.bing.com", "google.com", "www.google.com"}
SUB_SKIP = {"www", "en", "es", "us", "uk", "mx", "latam", "intl", "support"}


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = ''.join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9&/+\- ]", "", text)
    text = text.replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def nicify(text: str) -> str:
    if not text:
        return text
    tokens = re.split(r"[\s/]+", text.strip())
    nice = []
    for tok in tokens:
        if tok.isupper() and len(tok) <= 3:
            nice.append(tok)
        elif tok.isdigit():
            nice.append(tok)
        else:
            nice.append(tok.capitalize())
    return " ".join(nice)


def score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    jw = JaroWinkler.normalized_similarity(a, b) * 100
    ts = fuzz.token_sort_ratio(a, b)
    return (jw + ts) / 2.0


def label(score_value: float) -> str:
    if score_value >= HIGH:
        return "HIGH"
    if score_value >= MED:
        return "MED"
    return "LOW"


def save_cache():
    CACHE_FILE.write_text(json.dumps(SOURCE_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if 'duckduckgo.com/l/?' in href:
        from urllib.parse import parse_qs, urlparse, unquote
        qs = parse_qs(urlparse(href).query)
        uddg = qs.get("uddg")
        if uddg:
            return unquote(uddg[0])
    if href.startswith("/l/?"):
        from urllib.parse import parse_qs, urlparse, unquote
        qs = parse_qs(urlparse(href).query)
        uddg = qs.get("uddg")
        if uddg:
            return unquote(uddg[0])
    if href.startswith("http"):
        return href
    return ""


def domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    if not url:
        return ""
    netloc = urlparse(url).netloc.lower()
    if not netloc:
        return ""
    parts = [p for p in netloc.split('.') if p and p not in SUB_SKIP]
    return ".".join(parts) if parts else netloc


def lookup_source(query: str) -> str:
    key = query.lower().strip()
    if key in SOURCE_CACHE:
        return SOURCE_CACHE[key]
    try:
        resp = SESSION.get("https://duckduckgo.com/html/", params={"q": query}, timeout=12)
        resp.raise_for_status()
    except Exception as exc:
        SOURCE_CACHE[key] = "PENDING"
        FAILED_QUERIES.append(f"{query}: {exc}")
        return "PENDING"
    soup = BeautifulSoup(resp.text, "html.parser")
    url = "PENDING"
    for a in soup.select("a.result__a"):
        resolved = resolve_href(a.get("href"))
        dom = domain_from_url(resolved)
        if dom and dom not in STOP_DOMAINS:
            url = resolved
            break
    SOURCE_CACHE[key] = url
    return url


def connect():
    conn = mysql.connector.connect(**DB_CFG)
    conn.autocommit = False
    return conn, conn.cursor(dictionary=True)


def discover_schema(cur):
    sql = (
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND (column_name LIKE '%%marca%%' OR column_name LIKE '%%brand%%' "
        "OR column_name LIKE '%%modelo%%' OR column_name LIKE '%%model%%') ORDER BY table_name"
    )
    cur.execute(sql, (DB_CFG["database"],))
    df = pd.DataFrame(cur.fetchall())
    df.to_csv(OUTPUT_DIR / "schema_brand_model_columns.csv", index=False)
    return df


def detect_ingreso(cur):
    info = {"has_text": False, "references_devices": False}
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='ingresos'", (DB_CFG["database"],))
    for row in cur.fetchall():
        col = row.get("column_name") if isinstance(row, dict) else row[0]
        if col and ("marca" in col.lower() or "modelo" in col.lower()):
            info["has_text"] = True
    cur.execute(
        "SELECT COUNT(*) AS total FROM information_schema.key_column_usage "
        "WHERE table_schema=%s AND table_name='ingresos' AND referenced_table_name='devices'",
        (DB_CFG["database"],),
    )
    info["references_devices"] = cur.fetchone()["total"] > 0
    return info


def fetch_brands(cur):
    sql = (
        "SELECT m.id AS marca_id, m.nombre AS alias, COUNT(DISTINCT d.id) AS device_count, "
        "COUNT(DISTINCT mo.id) AS model_count FROM marcas m "
        "LEFT JOIN devices d ON d.marca_id = m.id "
        "LEFT JOIN models mo ON mo.marca_id = m.id "
        "GROUP BY m.id, m.nombre ORDER BY device_count DESC, m.nombre"
    )
    cur.execute(sql)
    return cur.fetchall()


def build_brand_clusters(rows):
    clusters = {}
    alias_matches = []
    brand_map = {}
    for row in rows:
        alias = (row["alias"] or "").strip()
        if not alias:
            continue
        norm = normalize(alias)
        best_key = None
        best_score = -1
        for canon, data in clusters.items():
            s = score(norm, data["norm"])
            if s > best_score:
                best_score = s
                best_key = canon
        if best_key is None or best_score < MED:
            canonical = nicify(alias)
            clusters[canonical] = {
                "norm": norm,
                "anchor_brand_id": row["marca_id"],
                "aliases": [],
                "source_url": "PENDING",
            }
            best_key = canonical
            best_score = 100.0
        entry = clusters[best_key]
        match = {
            "alias": alias,
            "canonical": best_key,
            "score": best_score,
            "label": label(best_score),
            "marca_id": row["marca_id"],
            "device_count": row["device_count"],
            "model_count": row["model_count"],
        }
        entry["aliases"].append(match)
        if match["label"] == "LOW":
            PENDING_LOW.append({"brand": best_key, "alias": alias, "canonical": best_key, "score": best_score})
        brand_map[row["marca_id"]] = best_key
        alias_matches.append(match)
    return clusters, alias_matches, brand_map


def persist_canonical_brands(conn, cur, clusters):
    for canonical, data in clusters.items():
        url = lookup_source(f"{canonical} medical equipment")
        if url == "PENDING":
            url = lookup_source(f"{canonical} manufacturer")
        data["source_url"] = url
        cur.execute(
            "INSERT INTO canonical_brands (name, source_url) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE source_url=VALUES(source_url)",
            (canonical, url),
        )
    conn.commit()
    cur.execute("SELECT id, name FROM canonical_brands")
    return {row["name"]: row["id"] for row in cur.fetchall()}


def persist_brand_aliases(conn, cur, alias_matches, canonical_ids):
    for match in alias_matches:
        canon_id = canonical_ids.get(match["canonical"])
        if canon_id is None:
            continue
        cur.execute(
            "INSERT INTO brand_aliases (alias, brand_id, confidence, method, notes) "
            "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
            "brand_id=VALUES(brand_id), confidence=VALUES(confidence), method=VALUES(method), notes=VALUES(notes)",
            (
                match["alias"],
                canon_id,
                float(f"{match['score']:.2f}"),
                "JW+TokenSort",
                f"devices={match['device_count']},models={match['model_count']}",
            ),
        )
    conn.commit()


def log_change(cur, table, pk, column, old, new, confidence, method, evidence, note):
    cur.execute(
        "INSERT INTO normalization_log (table_name, pk_value, column_name, old_value, new_value, confidence, method, evidence_url, note) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            table,
            str(pk),
            column,
            old,
            new,
            float(f"{confidence:.2f}"),
            method,
            evidence,
            note,
        ),
    )


def update_brand_names(conn, cur, clusters):
    stats = Counter()
    for canonical, data in clusters.items():
        anchor = data["anchor_brand_id"]
        if anchor is None:
            continue
        cur.execute("SELECT nombre FROM marcas WHERE id=%s", (anchor,))
        row = cur.fetchone()
        if not row:
            continue
        current = row["nombre"]
        if current == canonical:
            continue
        conf = score(normalize(current), data["norm"])
        if label(conf) == "LOW":
            continue
        cur.execute("UPDATE marcas SET nombre=%s WHERE id=%s", (canonical, anchor))
        log_change(cur, "marcas", anchor, "nombre", current, canonical, conf, "JW+TokenSort", data["source_url"], "Normalización de marca")
        conn.commit()
        stats[label(conf)] += 1
    return stats


def reassign_brand_ids(conn, cur, clusters):
    stats = Counter()
    for canonical, data in clusters.items():
        anchor = data["anchor_brand_id"]
        if anchor is None:
            continue
        evidence = data["source_url"]
        for match in data["aliases"]:
            alias_id = match["marca_id"]
            if alias_id == anchor:
                continue
            confidence = match["score"]
            cur.execute("SELECT id, nombre FROM models WHERE marca_id=%s", (alias_id,))
            model_rows = cur.fetchall()
            for model in model_rows:
                model_id = model["id"]
                nombre = model["nombre"]
                cur.execute("SELECT id FROM models WHERE marca_id=%s AND nombre=%s LIMIT 1", (anchor, nombre))
                existing = cur.fetchone()
                if existing:
                    existing_id = existing["id"]
                    cur.execute("SELECT id FROM devices WHERE model_id=%s", (model_id,))
                    for device in cur.fetchall():
                        cur.execute("UPDATE devices SET model_id=%s WHERE id=%s", (existing_id, device["id"]))
                        log_change(cur, "devices", device["id"], "model_id", str(model_id), str(existing_id), confidence, "JW+TokenSort", evidence, "Merge modelo duplicado")
                        stats[label(confidence)] += 1
                    log_change(cur, "models", model_id, "__delete__", f"marca_id={alias_id},nombre={nombre}", f"merged->{existing_id}", confidence, "JW+TokenSort", evidence, "Eliminado modelo duplicado")
                    cur.execute("DELETE FROM models WHERE id=%s", (model_id,))
                else:
                    cur.execute("UPDATE models SET marca_id=%s WHERE id=%s", (anchor, model_id))
                    log_change(cur, "models", model_id, "marca_id", str(alias_id), str(anchor), confidence, "JW+TokenSort", evidence, "Reasignación de marca")
                    stats[label(confidence)] += 1
            conn.commit()
            cur.execute("SELECT id FROM devices WHERE marca_id=%s", (alias_id,))
            for device in cur.fetchall():
                cur.execute("UPDATE devices SET marca_id=%s WHERE id=%s", (anchor, device["id"]))
                log_change(cur, "devices", device["id"], "marca_id", str(alias_id), str(anchor), confidence, "JW+TokenSort", evidence, "Reasignación de marca")
                stats[label(confidence)] += 1
            conn.commit()
    return stats


def fetch_models(conn):
    sql = (
        "SELECT mo.id AS model_id, mo.nombre AS alias, mo.marca_id, m.nombre AS marca, COUNT(d.id) AS device_count "
        "FROM models mo LEFT JOIN marcas m ON m.id = mo.marca_id "
        "LEFT JOIN devices d ON d.model_id = mo.id "
        "GROUP BY mo.id, mo.nombre, mo.marca_id, m.nombre"
    )
    return pd.read_sql(sql, conn)


def cluster_models(df, clusters, brand_map):
    model_aliases = []
    low_pending = []
    for marca_id, group in df.groupby("marca_id"):
        canonical_name = brand_map.get(marca_id)
        if not canonical_name or canonical_name not in clusters:
            continue
        brand_entry = clusters[canonical_name]
        within = {}
        for _, row in group.iterrows():
            alias = (row["alias"] or "").strip()
            if not alias:
                continue
            norm = normalize(alias)
            best_key = None
            best_score = -1
            for canon, data in within.items():
                s = score(norm, data["norm"])
                if s > best_score:
                    best_score = s
                    best_key = canon
            if best_key is None or best_score < MED:
                canon_model = nicify(alias)
                within[canon_model] = {"norm": norm, "matches": []}
                best_key = canon_model
                best_score = 100.0
            within[best_key]["matches"].append(
                {
                    "model_id": int(row["model_id"]),
                    "alias": alias,
                    "score": best_score,
                    "label": label(best_score),
                    "brand_canonical": canonical_name,
                    "source_url": brand_entry["source_url"],
                }
            )
        for canon_model, data in within.items():
            model_aliases.append((canonical_name, canon_model, data["matches"]))
            for match in data["matches"]:
                if match["label"] == "LOW":
                    low_pending.append({
                        "brand": canonical_name,
                        "alias": match["alias"],
                        "canonical": canon_model,
                        "score": match["score"],
                    })
    return model_aliases, low_pending


def persist_canonical_models(conn, cur, canonical_ids, clusters, model_aliases):
    for brand_name, model_name, matches in model_aliases:
        brand_id = canonical_ids.get(brand_name)
        if brand_id is None:
            continue
        source_url = clusters[brand_name]["source_url"]
        cur.execute(
            "INSERT INTO canonical_models (brand_id, name, source_url) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE source_url=VALUES(source_url)",
            (brand_id, model_name, source_url),
        )
    conn.commit()


def update_models(conn, cur, model_aliases, clusters):
    stats = Counter()
    for brand_name, model_name, matches in model_aliases:
        source_url = clusters[brand_name]["source_url"]
        for match in matches:
            if match["label"] == "LOW":
                continue
            cur.execute("SELECT nombre, marca_id FROM models WHERE id=%s", (match["model_id"],))
            row = cur.fetchone()
            if not row:
                continue
            current = row["nombre"]
            marca_id = row["marca_id"]
            if current == model_name:
                continue
            cur.execute("SELECT id FROM models WHERE marca_id=%s AND nombre=%s LIMIT 1", (marca_id, model_name))
            existing = cur.fetchone()
            if existing:
                existing_id = existing["id"]
                cur.execute("SELECT id FROM devices WHERE model_id=%s", (match["model_id"],))
                for device in cur.fetchall():
                    cur.execute("UPDATE devices SET model_id=%s WHERE id=%s", (existing_id, device["id"]))
                    log_change(cur, "devices", device["id"], "model_id", str(match["model_id"]), str(existing_id), match["score"], "JW+TokenSort", source_url, "Merge modelo duplicado")
                    stats[label(match["score"])] += 1
                log_change(cur, "models", match["model_id"], "__delete__", f"marca_id={marca_id},nombre={current}", f"merged->{existing_id}", match["score"], "JW+TokenSort", source_url, "Eliminado modelo duplicado")
                cur.execute("DELETE FROM models WHERE id=%s", (match["model_id"],))
            else:
                cur.execute("UPDATE models SET nombre=%s WHERE id=%s", (model_name, match["model_id"]))
                log_change(cur, "models", match["model_id"], "nombre", current, model_name, match["score"], "JW+TokenSort", source_url, "Normalización de modelo")
                stats[match["label"]] += 1
            conn.commit()
    return stats


def persist_model_aliases(conn, cur, canonical_ids, model_aliases):
    for brand_name, model_name, matches in model_aliases:
        brand_id = canonical_ids.get(brand_name)
        if brand_id is None:
            continue
        cur.execute("SELECT id FROM canonical_models WHERE brand_id=%s AND name=%s", (brand_id, model_name))
        row = cur.fetchone()
        if not row:
            continue
        canonical_model_id = row["id"]
        for match in matches:
            cur.execute(
                "INSERT INTO model_aliases (alias, model_id, brand_id, confidence, method, notes) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "model_id=VALUES(model_id), confidence=VALUES(confidence), method=VALUES(method), notes=VALUES(notes)",
                (
                    match["alias"],
                    canonical_model_id,
                    brand_id,
                    float(f"{match['score']:.2f}"),
                    "JW+TokenSort",
                    f"brand={brand_name}",
                ),
            )
    conn.commit()


def backfill_device_brand(conn, cur):
    cur.execute(
        "SELECT d.id AS device_id, mo.marca_id AS model_brand FROM devices d "
        "LEFT JOIN models mo ON mo.id = d.model_id "
        "WHERE d.marca_id IS NULL AND mo.marca_id IS NOT NULL"
    )
    rows = cur.fetchall()
    if not rows:
        return 0
    count = 0
    for row in rows:
        cur.execute("UPDATE devices SET marca_id=%s WHERE id=%s", (row["model_brand"], row["device_id"]))
        log_change(cur, "devices", row["device_id"], "marca_id", "NULL", str(row["model_brand"]), 100.0, "ModelBrandBackfill", "", "Backfill desde modelo")
        count += 1
    conn.commit()
    return count


def export_reports(conn, start_ts):
    paths = {}
    df_changes = pd.read_sql(
        "SELECT table_name, pk_value, column_name, old_value, new_value, confidence, method, evidence_url, ts "
        "FROM normalization_log WHERE ts >= %s ORDER BY ts",
        conn,
        params=(start_ts.strftime("%Y-%m-%d %H:%M:%S"),),
    )
    path_changes = OUTPUT_DIR / "reporte_cambios.csv"
    df_changes.to_csv(path_changes, index=False)
    paths["reporte_cambios"] = path_changes

    df_pending = pd.DataFrame(PENDING_LOW)
    path_pending = OUTPUT_DIR / "pendientes_revision.csv"
    df_pending.to_csv(path_pending, index=False)
    paths["pendientes_revision"] = path_pending

    resumen = []
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS total FROM marcas")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS conformes FROM marcas WHERE nombre IN (SELECT name FROM canonical_brands)")
    conformes = cur.fetchone()["conformes"]
    resumen.append({"tabla": "marcas", "columna": "nombre", "total": total, "conformes": conformes, "porcentaje": round((conformes/total*100) if total else 100, 2)})

    cur.execute("SELECT COUNT(*) AS total FROM models")
    total_models = cur.fetchone()["total"]
    cur.execute(
        "SELECT COUNT(*) AS conformes FROM models mo "
        "JOIN marcas m ON m.id = mo.marca_id "
        "JOIN canonical_brands cb ON cb.name = m.nombre "
        "JOIN canonical_models cm ON cm.brand_id = cb.id AND cm.name = mo.nombre"
    )
    conformes_models = cur.fetchone()["conformes"]
    resumen.append({"tabla": "models", "columna": "nombre", "total": total_models, "conformes": conformes_models, "porcentaje": round((conformes_models/total_models*100) if total_models else 100, 2)})

    cur.execute("SELECT COUNT(*) AS total FROM devices")
    total_dev = cur.fetchone()["total"]
    cur.execute(
        "SELECT COUNT(*) AS conformes FROM devices d "
        "LEFT JOIN marcas m ON m.id = d.marca_id "
        "LEFT JOIN canonical_brands cb ON cb.name = m.nombre "
        "LEFT JOIN models mo ON mo.id = d.model_id "
        "LEFT JOIN canonical_models cm ON cm.brand_id = cb.id AND cm.name = mo.nombre "
        "WHERE d.marca_id IS NOT NULL AND cb.id IS NOT NULL AND (mo.id IS NULL OR cm.id IS NOT NULL)"
    )
    conformes_dev = cur.fetchone()["conformes"]
    resumen.append({"tabla": "devices", "columna": "marca_id/model_id", "total": total_dev, "conformes": conformes_dev, "porcentaje": round((conformes_dev/total_dev*100) if total_dev else 100, 2)})

    df_resumen = pd.DataFrame(resumen)
    path_resumen = OUTPUT_DIR / "resumen_conformidad.csv"
    df_resumen.to_csv(path_resumen, index=False)
    paths["resumen_conformidad"] = path_resumen

    readme = OUTPUT_DIR / "README_normalizacion.md"
    with readme.open("w", encoding="utf-8") as fh:
        fh.write(f"# Normalización de marcas y modelos\n\n")
        fh.write(f"- Fecha de ejecución: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.write(f"- Umbrales: HIGH≥{HIGH}, MED≥{MED}\n")
        fh.write(f"- Alias marcas procesados: {SUMMARY['brand_total']}\n")
        fh.write(f"- Alias modelos procesados: {SUMMARY['model_total']}\n")
        fh.write(f"- Cambios aplicados HIGH: {SUMMARY['high']} | MED: {SUMMARY['med']}\n")
        if FAILED_QUERIES:
            fh.write("\n## Incidencias\n")
            for query in FAILED_QUERIES:
                fh.write(f"- {query}\n")
        fh.write("\n## Fuentes\n")
        for canonical, data in sorted(CLUSTERS.items()):
            fh.write(f"- {canonical}: {data['source_url']}\n")
        if PENDING_LOW:
            fh.write("\n## Pendientes\nListado en `pendientes_revision.csv`.\n")
    paths["readme"] = readme
    return paths


def check_ingresos(conn):
    sql = (
        "SELECT i.id AS ingreso_id, m.nombre AS marca, mo.nombre AS modelo "
        "FROM ingresos i LEFT JOIN devices d ON d.id = i.device_id "
        "LEFT JOIN marcas m ON m.id = d.marca_id "
        "LEFT JOIN canonical_brands cb ON cb.name = m.nombre "
        "LEFT JOIN models mo ON mo.id = d.model_id "
        "LEFT JOIN canonical_models cm ON cm.brand_id = cb.id AND cm.name = mo.nombre "
        "WHERE cb.id IS NULL OR (mo.id IS NOT NULL AND cm.id IS NULL)"
    )
    df = pd.read_sql(sql, conn)
    return df


CLUSTERS = {}
ALIAS_MATCHES = []
BRAND_MAP = {}
PENDING_LOW = []
SUMMARY = {"high": 0, "med": 0, "brand_total": 0, "model_total": 0}
FAILED_QUERIES = []


def main():
    start_ts = datetime.utcnow()
    conn, cur = connect()
    try:
        discover_schema(cur)
        detect_ingreso(cur)
        brands = fetch_brands(cur)
        global CLUSTERS, ALIAS_MATCHES, BRAND_MAP
        CLUSTERS, ALIAS_MATCHES, BRAND_MAP = build_brand_clusters(brands)
        SUMMARY["brand_total"] = len(ALIAS_MATCHES)
        canonical_ids = persist_canonical_brands(conn, cur, CLUSTERS)
        persist_brand_aliases(conn, cur, ALIAS_MATCHES, canonical_ids)
        stats = update_brand_names(conn, cur, CLUSTERS)
        SUMMARY["high"] += stats.get("HIGH", 0)
        SUMMARY["med"] += stats.get("MED", 0)
        stats_reassign = reassign_brand_ids(conn, cur, CLUSTERS)
        SUMMARY["high"] += stats_reassign.get("HIGH", 0)
        SUMMARY["med"] += stats_reassign.get("MED", 0)
        models_df = fetch_models(conn)
        model_aliases, model_pending = cluster_models(models_df, CLUSTERS, BRAND_MAP)
        PENDING_LOW.extend(model_pending)
        SUMMARY["model_total"] = sum(len(m[2]) for m in model_aliases)
        persist_canonical_models(conn, cur, canonical_ids, CLUSTERS, model_aliases)
        stats_models = update_models(conn, cur, model_aliases, CLUSTERS)
        SUMMARY["high"] += stats_models.get("HIGH", 0)
        SUMMARY["med"] += stats_models.get("MED", 0)
        persist_model_aliases(conn, cur, canonical_ids, model_aliases)
        backfilled = backfill_device_brand(conn, cur)
        SUMMARY["high"] += backfilled
        reports = export_reports(conn, start_ts)
        ingresos_df = check_ingresos(conn)
    finally:
        cur.close()
        conn.close()
        save_cache()

    conformidad = pd.read_csv(OUTPUT_DIR / "resumen_conformidad.csv")
    promedio = conformidad["porcentaje"].mean()
    print("==== Normalización completada ====")
    print(f"Alias marcas HIGH/MED/LOW: {sum(1 for m in ALIAS_MATCHES if m['label']=='HIGH')} / {sum(1 for m in ALIAS_MATCHES if m['label']=='MED')} / {sum(1 for m in ALIAS_MATCHES if m['label']=='LOW')}")
    print(f"Alias modelos LOW pendientes: {len(PENDING_LOW)}")
    print(f"Cambios aplicados HIGH: {SUMMARY['high']} | MED: {SUMMARY['med']}")
    print(f"% conformidad promedio: {promedio:.2f}%")
    if ingresos_df.empty:
        print("0 filas fuera de catálogo en Ingresos")
    else:
        print(f"Ingresos fuera de catálogo: {len(ingresos_df)}")
        print(ingresos_df.head(10).to_string(index=False))
    print("Reportes generados")
    print(f"- {OUTPUT_DIR / 'reporte_cambios.csv'}")
    print(f"- {OUTPUT_DIR / 'pendientes_revision.csv'}")
    print(f"- {OUTPUT_DIR / 'resumen_conformidad.csv'}")
    print(f"- {OUTPUT_DIR / 'README_normalizacion.md'}")


if __name__ == "__main__":
    main()

