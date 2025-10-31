#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualizar modelos de equipos LONGFIAN en SR usando mapeo por número interno MG
desde el archivo Excel 'docs/Copia Para Consultar MADRE 2025.xlsx'.

Fuente Excel (columnas):
- Columna H: número interno (MG####)
- Columna F: modelo del equipo

Lógica:
- Construir un mapa MG -> modelo (de Excel) y normalizar el modelo LONGFIAN
  a la forma canónica (JAY-5, JAY-5Q, JAY-10, JAY-10D, JAY-120, JSB-1200).
- En SR, seleccionar dispositivos cuya marca sea Longfian y cuyo numero_serie
  contenga 'MG'. Extraer el código MG (normalizado) y, si hay modelo canónico
  en el mapa, reasignar el model_id al correspondiente.

Modo por defecto: dry-run (no aplica). Con --apply aplica los cambios.

Conexión:
- Postgres via env: POSTGRES_HOST/PORT/DB/USER/PASSWORD (con defaults razonables).

Salida:
- scripts/output/longfian_from_mg_excel_plan.csv (device_id, NS, modelo_actual, modelo_nuevo, mg_code, modelo_excel)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl  # type: ignore
import psycopg  # type: ignore


EXCEL_PATH = Path("docs/Copia Para Consultar MADRE 2025.xlsx")
OUT_DIR = Path("scripts/output")
OUT_CSV = OUT_DIR / "longfian_from_mg_excel_plan.csv"


def env(name: str, default: Optional[str] = None) -> Optional[str]:
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


def norm_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s2 = s.strip().upper()
    s2 = re.sub(r"\s+", " ", s2)
    return s2


def norm_key_alnum(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]", "", norm_text(s))


def extract_mg_key(s: Optional[str]) -> str:
    # Devuelve clave normalizada tipo 'MG1234' a partir de strings con MG 1234 / MG-1234 / mg1234
    if not s:
        return ""
    t = norm_text(s)
    m = re.search(r"\bMG\s*-?\s*([0-9]+)\b", t)
    if m:
        return f"MG{m.group(1)}"
    # fallback: si viene como 'MG1234' pegado
    m = re.search(r"\bMG([0-9]+)\b", t)
    if m:
        return f"MG{m.group(1)}"
    return ""


# Normalización de modelos LONGFIAN (idéntico al usado en Access)
LONGFIAN_OVERRIDES: Dict[str, str] = {
    "JAY5": "JAY-5",
    "JAY5Q": "JAY-5Q",
    "JAY10": "JAY-10",
    "JAY10D": "JAY-10D",
    "JAY120": "JAY-120",
    "JSB1200": "JSB-1200",
}


def canonical_longfian_model(raw: Optional[str]) -> str:
    t = norm_text(raw)
    t = re.sub(r"\s*-\s*", "-", t)
    t = re.sub(r"\s*/\s*", "/", t)
    k = norm_key_alnum(t)
    if k in LONGFIAN_OVERRIDES:
        return LONGFIAN_OVERRIDES[k]
    m = re.match(r"^JAY\s*-?\s*([0-9]{1,3}[A-Z]?)$", t)
    if m:
        return f"JAY-{m.group(1)}"
    return t


def load_mg_map_from_excel(xlsx_path: Path) -> Dict[str, str]:
    if not xlsx_path.exists():
        raise SystemExit(f"No se encontró el Excel: {xlsx_path}")
    wb = openpyxl.load_workbook(str(xlsx_path), data_only=True, read_only=True)
    ws = wb.active
    mg_to_model: Dict[str, str] = {}
    # Columnas: F=6 (modelo), H=8 (MG)
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        try:
            model = str(row[5] or "").strip()  # F
            mgval = str(row[7] or "").strip()  # H
        except Exception:
            continue
        if not mgval:
            continue
        key = extract_mg_key(mgval)
        if not key:
            continue
        if not model:
            continue
        mg_to_model[key] = canonical_longfian_model(model)
    wb.close()
    return mg_to_model


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_model(cur, marca_id: int, nombre: str) -> int:
    cur.execute(
        "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
        (marca_id, nombre),
    )
    r = cur.fetchone()
    if r:
        return int(r[0])
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (marca_id, nombre))
    return int(cur.fetchone()[0])


def model_name_by_id(cur) -> Dict[int, str]:
    cur.execute("SELECT id, nombre FROM models")
    return {int(r[0]): str(r[1]) for r in cur.fetchall() or []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica cambios en SR (por defecto: dry-run)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Cargando mapa MG->modelo desde Excel...")
    mg_map = load_mg_map_from_excel(EXCEL_PATH)
    print(f"MG únicos en Excel: {len(mg_map)}")

    cn = connect_pg()
    if args.apply:
        cn.autocommit = False
    try:
        with cn.cursor() as cur:
            bid = brand_id(cur, "Longfian") or brand_id(cur, "LONGFIAN")
            if not bid:
                raise SystemExit("Marca 'Longfian' no encontrada en SR")

            cur.execute(
                """
                SELECT d.id, d.model_id, COALESCE(TRIM(d.numero_serie), '') AS ns
                FROM devices d
                WHERE d.marca_id=%s AND UPPER(d.numero_serie) LIKE '%%MG%%'
                """,
                (bid,),
            )
            rows = cur.fetchall() or []
            print(f"Devices LONGFIAN con MG en NS: {len(rows)}")

            mid2name = model_name_by_id(cur)
            planned: List[List[str]] = []
            updated = 0
            ensured: Dict[str, int] = {}

            for did, mid, ns in rows:
                mg_key = extract_mg_key(ns)
                if not mg_key:
                    continue
                excel_model = mg_map.get(mg_key)
                if not excel_model:
                    continue
                # normalizar LONGFIAN
                canon_model = canonical_longfian_model(excel_model)
                if canon_model not in ensured:
                    ensured[canon_model] = ensure_model(cur, bid, canon_model)
                dst_mid = ensured[canon_model]
                cur_name = mid2name.get(int(mid) if mid is not None else -1, "")
                if mid == dst_mid:
                    continue
                planned.append([str(int(did)), str(ns), cur_name, canon_model, mg_key, excel_model])
                if args.apply:
                    cur.execute("UPDATE devices SET model_id=%s WHERE id=%s", (dst_mid, int(did)))
                    updated += 1

            # Guardar plan
            with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
                cw = csv.writer(f)
                cw.writerow(["device_id","numero_serie","modelo_actual","modelo_nuevo","mg_key","modelo_excel"])
                for row in planned:
                    cw.writerow(row)

            if args.apply:
                cn.commit()

            print("=== LONGFIAN desde MG Excel ===")
            print(f"Plan de cambios: {OUT_CSV}")
            print(f"Devices con cambio planeado: {len(planned)}")
            if args.apply:
                print(f"Actualizados: {updated}")
            else:
                print("Modo: DRY-RUN (sin cambios)")
    finally:
        try:
            cn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

