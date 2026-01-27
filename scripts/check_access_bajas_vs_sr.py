import argparse
import csv
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pyodbc  # type: ignore
import psycopg

DEFAULT_ACCESS_DB = r"Z:\Servicio Tecnico\1_SISTEMA REPARACIONES\2025-06\Tablas2025 MG-SEPID 2.0.accdb"
DEFAULT_ENV_FILE = ".env.prod"
DEFAULT_OUT = "scripts/output/access_bajas_vs_sr.csv"
DEFAULT_OUT_MISMATCH = "scripts/output/access_bajas_vs_sr_mismatch.csv"
CHUNK_SIZE = 1000

NEG_WORDS = {
    "presion",
    "aspiracion",
    "concentracion",
    "tension",
    "bateria",
    "baterias",
    "carga",
    "voltaje",
    "vacio",
    "revoluciones",
    "rpm",
    "mmhg",
}

STRONG_RE = re.compile(
    r"\b(se\s+da\s+de\s+baja|se\s+dio\s+de\s+baja|dar\s+de\s+baja|dado\s+de\s+baja|"
    r"dada\s+de\s+baja|para\s+dar\s+de\s+baja|se\s+recomienda\s+dar\s+de\s+baja|"
    r"desguac\w*)\b"
)


@dataclass(frozen=True)
class AccessRow:
    id: int
    estado_num: Optional[int]
    informe_final: str
    reg_desc: str
    marca: str
    modelo: str
    numero_serie: str
    n_de_control: str


def normalize_text(value: str) -> str:
    norm = unicodedata.normalize("NFKD", value)
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch))
    return norm.lower()


def normalize_tokens(value: str) -> List[str]:
    norm = normalize_text(value)
    norm = re.sub(r"[^a-z0-9]+", " ", norm)
    return [t for t in norm.split() if t]


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(text.split()).strip()


def is_baja_text(value: Optional[str]) -> bool:
    if not value:
        return False
    norm = normalize_text(str(value))
    if not norm:
        return False
    if STRONG_RE.search(norm):
        return True
    if "baja" not in norm:
        return False

    toks = normalize_tokens(str(value))
    for i, tok in enumerate(toks):
        if tok != "baja":
            continue
        prev = toks[i - 1] if i > 0 else ""
        prev2 = toks[i - 2] if i > 1 else ""
        next = toks[i + 1] if i + 1 < len(toks) else ""
        next2 = toks[i + 2] if i + 2 < len(toks) else ""

        if prev == "de" and prev2 in {"dar", "dado", "dada", "da", "dio", "recomienda", "para", "se"}:
            return True
        if next == "por":
            return True

        if next in NEG_WORDS or prev in NEG_WORDS:
            continue
        if next == "de" and next2 in NEG_WORDS:
            continue
        if prev == "de" and prev2 in NEG_WORDS:
            continue

        return True
    return False


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        env[key] = val
    return env


def env_get(env: Dict[str, str], key: str, default: str) -> str:
    val = os.getenv(key)
    if val:
        return val
    return env.get(key) or default


def connect_access(db_path: str):
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={db_path};"
    return pyodbc.connect(conn_str, autocommit=True)


def connect_pg(env: Dict[str, str]):
    dsn = (
        f"host={env_get(env, 'POSTGRES_HOST', '127.0.0.1')} "
        f"port={env_get(env, 'POSTGRES_PORT', '5432')} "
        f"dbname={env_get(env, 'POSTGRES_DB', 'servicio_tecnico')} "
        f"user={env_get(env, 'POSTGRES_USER', 'sepid')} "
        f"password={env_get(env, 'POSTGRES_PASSWORD', '')}"
    )
    return psycopg.connect(dsn)


def find_reg_desc_column(cn) -> Optional[str]:
    cur = cn.cursor()
    cols = [row.column_name for row in cur.columns(table="RegistrosdeServicio")]
    if not cols:
        return None
    for col in cols:
        norm = normalize_text(col)
        if "descripcion" in norm and "problema" in norm:
            return col
    for col in cols:
        norm = normalize_text(col)
        if "descripcion" in norm or "descr" in norm:
            return col
    return None


def fetch_access_rows(db_path: str) -> List[AccessRow]:
    cn = connect_access(db_path)
    try:
        desc_col = find_reg_desc_column(cn)
        desc_map: Dict[int, List[str]] = {}
        if desc_col:
            safe_col = desc_col.replace("]", "]]")
            cur = cn.cursor()
            cur.execute(f"SELECT [Id], [{safe_col}] FROM [RegistrosdeServicio]")
            for row in cur.fetchall():
                rid = row[0]
                if rid is None:
                    continue
                desc = clean_text(row[1])
                if not desc:
                    continue
                desc_map.setdefault(int(rid), []).append(desc)

        cur = cn.cursor()
        cur.execute(
            "SELECT [Id], [InformeFinal], [Estado], [Marca], [Modelo], [NumeroSerie], [NdeControl] "
            "FROM [Servicio]"
        )
        rows: List[AccessRow] = []
        for row in cur.fetchall():
            rid = row[0]
            if rid is None:
                continue
            estado_raw = row[2]
            estado_num = None
            if estado_raw is not None:
                try:
                    estado_num = int(str(estado_raw).strip())
                except Exception:
                    estado_num = None
            reg_desc = " | ".join(desc_map.get(int(rid), []))
            rows.append(
                AccessRow(
                    id=int(rid),
                    estado_num=estado_num,
                    informe_final=clean_text(row[1]),
                    reg_desc=reg_desc,
                    marca=clean_text(row[3]),
                    modelo=clean_text(row[4]),
                    numero_serie=clean_text(row[5]),
                    n_de_control=clean_text(row[6]),
                )
            )
        return rows
    finally:
        try:
            cn.close()
        except Exception:
            pass


def chunked(items: Sequence[int], size: int) -> Iterable[List[int]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def fetch_pg_info(pg, ids: Sequence[int]) -> Dict[int, Tuple[str, str]]:
    info: Dict[int, Tuple[str, str]] = {}
    if not ids:
        return info
    for chunk in chunked(list(ids), CHUNK_SIZE):
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.estado::text, COALESCE(l.nombre, '')
                FROM ingresos i
                LEFT JOIN locations l ON l.id = i.ubicacion_id
                WHERE i.id = ANY(%s)
                """,
                (chunk,),
            )
            for row in cur.fetchall():
                info[int(row[0])] = (str(row[1]), str(row[2]))
    return info


def build_sources(row: AccessRow) -> Tuple[bool, bool, bool, List[str]]:
    sources: List[str] = []
    estado_baja = row.estado_num == 8
    informe_baja = is_baja_text(row.informe_final)
    reg_baja = is_baja_text(row.reg_desc)
    if estado_baja:
        sources.append("estado=8")
    if informe_baja:
        sources.append("informe_final")
    if reg_baja:
        sources.append("reg_desc")
    return estado_baja, informe_baja, reg_baja, sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cruza bajas detectadas en Access vs estado en SR (Postgres)."
    )
    parser.add_argument("--access-db", default=DEFAULT_ACCESS_DB, help="Ruta al .accdb de Access")
    parser.add_argument("--env", default=DEFAULT_ENV_FILE, help="Ruta al .env con POSTGRES_*")
    parser.add_argument("--out", default=DEFAULT_OUT, help="CSV de salida con el detalle completo")
    parser.add_argument(
        "--out-mismatch",
        default=DEFAULT_OUT_MISMATCH,
        help="CSV de salida solo con bajas en Access sin baja en SR o faltantes",
    )
    args = parser.parse_args()

    access_db = args.access_db
    if not Path(access_db).exists():
        print(f"ERROR: Access no encontrado: {access_db}")
        return 1

    env_path = Path(args.env)
    env = load_env_file(env_path) if env_path else {}
    if env_path and not env_path.exists():
        print(f"WARN: No se encontro env en {env_path}; usando variables de entorno actuales.")

    access_rows = fetch_access_rows(access_db)
    total_access = len(access_rows)

    bajas: List[Tuple[AccessRow, bool, bool, bool, List[str]]] = []
    for row in access_rows:
        estado_baja, informe_baja, reg_baja, sources = build_sources(row)
        if sources:
            bajas.append((row, estado_baja, informe_baja, reg_baja, sources))

    baja_ids = sorted({row.id for row, *_ in bajas})

    try:
        pg = connect_pg(env)
    except Exception:
        print("ERROR: No se pudo conectar a Postgres. Verifique POSTGRES_* en el env.")
        return 1

    try:
        pg_info = fetch_pg_info(pg, baja_ids)
    finally:
        try:
            pg.close()
        except Exception:
            pass

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_mismatch_path = Path(args.out_mismatch) if args.out_mismatch else None
    if out_mismatch_path:
        out_mismatch_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "access_id",
        "access_estado_num",
        "access_informe_final",
        "access_reg_desc",
        "access_marca",
        "access_modelo",
        "access_numero_serie",
        "access_n_de_control",
        "access_baja_sources",
        "access_baja_from_estado",
        "access_baja_from_informe",
        "access_baja_from_reg_desc",
        "sr_estado",
        "sr_ubicacion",
        "sr_is_baja",
        "sr_missing",
    ]

    mismatch_rows: List[Dict[str, str]] = []
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row, estado_baja, informe_baja, reg_baja, sources in bajas:
            sr_estado = ""
            sr_ubic = ""
            sr_missing = "1"
            sr_is_baja = "0"
            if row.id in pg_info:
                sr_estado, sr_ubic = pg_info[row.id]
                sr_missing = "0"
                sr_is_baja = "1" if sr_estado == "baja" else "0"

            rec = {
                "access_id": str(row.id),
                "access_estado_num": "" if row.estado_num is None else str(row.estado_num),
                "access_informe_final": row.informe_final,
                "access_reg_desc": row.reg_desc,
                "access_marca": row.marca,
                "access_modelo": row.modelo,
                "access_numero_serie": row.numero_serie,
                "access_n_de_control": row.n_de_control,
                "access_baja_sources": ";".join(sources),
                "access_baja_from_estado": "1" if estado_baja else "0",
                "access_baja_from_informe": "1" if informe_baja else "0",
                "access_baja_from_reg_desc": "1" if reg_baja else "0",
                "sr_estado": sr_estado,
                "sr_ubicacion": sr_ubic,
                "sr_is_baja": sr_is_baja,
                "sr_missing": sr_missing,
            }
            writer.writerow(rec)
            if sr_missing == "1" or sr_is_baja != "1":
                mismatch_rows.append(rec)

    if out_mismatch_path:
        with out_mismatch_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in mismatch_rows:
                writer.writerow(rec)

    estado_baja_cnt = sum(1 for _, e, _, _, _ in bajas if e)
    informe_baja_cnt = sum(1 for _, _, i, _, _ in bajas if i)
    reg_baja_cnt = sum(1 for _, _, _, r, _ in bajas if r)
    missing_cnt = sum(1 for rec in mismatch_rows if rec["sr_missing"] == "1")
    not_baja_cnt = sum(1 for rec in mismatch_rows if rec["sr_missing"] == "0")

    print(f"Access filas totales: {total_access}")
    print(f"Bajas detectadas en Access: {len(bajas)} (ids unicos: {len(baja_ids)})")
    print(
        "Fuentes: estado=8=%d informe_final=%d reg_desc=%d"
        % (estado_baja_cnt, informe_baja_cnt, reg_baja_cnt)
    )
    print(f"En SR: faltantes={missing_cnt} no_baja={not_baja_cnt}")
    print(f"Reporte completo: {out_path}")
    if out_mismatch_path:
        print(f"Reporte solo pendientes: {out_mismatch_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
