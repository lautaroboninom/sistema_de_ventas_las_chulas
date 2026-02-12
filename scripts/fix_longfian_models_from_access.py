#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Corrige modelos LONGFIAN en el SR a partir de Access.

Qué hace:
- Lee Access (tabla Servicio) y extrae (NumeroSerie, Modelo) donde Marca='LONGFIAN'.
- Normaliza modelos LONGFIAN a su forma canónica: JAY-5, JAY-5Q, JAY-10, JAY-10D, JAY-120, JSB-1200.
- Conecta a Postgres (SR) y, por número de serie, reasigna cada device LONGFIAN al modelo canónico correspondiente.

Modo por defecto: dry-run (no actualiza). Con --apply aplica los cambios.

Conexiones:
- Access: Z:\Servicio Tecnico\1_SISTEMA REPARACIONES\2025-06\Tablas2025 MG-SEPID 2.0.accdb
- Postgres: variables POSTGRES_HOST/PORT/DB/USER/PASSWORD (o defaults).

Salida:
- scripts/output/longfian_access_to_sr_plan.csv (plan de cambios)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyodbc  # type: ignore
import psycopg  # type: ignore


ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
OUT_DIR = Path("scripts/output")
OUT_CSV = OUT_DIR / "longfian_access_to_sr_plan.csv"


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
    s2 = s2.replace("-", "-")
    return s2


def norm_key(s: Optional[str]) -> str:
    # clave insensible a espacios/guiones para serie/modelo
    if not s:
        return ""
    s2 = norm_text(s)
    s2 = re.sub(r"[^A-Z0-9]", "", s2)
    return s2


# Normalización de modelos LONGFIAN basada en scripts/normalize_service_brand_model.py
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
    k = norm_key(t)
    if k in LONGFIAN_OVERRIDES:
        return LONGFIAN_OVERRIDES[k]
    # Heurística básica JAY-<sufijo>
    m = re.match(r"^JAY\s*-?\s*([0-9]{1,3}[A-Z]?)$", t)
    if m:
        return f"JAY-{m.group(1)}"
    return t


@dataclass
class AccessRow:
    serial: str
    model: str
    fecha_ingreso: Optional[str]


def fetch_access_longfian() -> List[AccessRow]:
    cn = pyodbc.connect(
        f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};", autocommit=True
    )
    cur = cn.cursor()
    # Tomamos los LONGFIAN con serial no vacío, y nos quedamos con el último por fecha
    cur.execute(
        """
        SELECT [NumeroSerie], [Modelo], [Fecha Ingreso]
        FROM [Servicio]
        WHERE UCASE(TRIM([Marca]))='LONGFIAN' AND [NumeroSerie] IS NOT NULL AND TRIM([NumeroSerie])<>''
        ORDER BY [Fecha Ingreso] DESC
        """
    )
    rows: List[AccessRow] = []
    for r in cur.fetchall():
        serial = str(r[0] or "").strip()
        model = str(r[1] or "").strip()
        fecha = None
        try:
            fecha = str(r[2]) if r[2] is not None else None
        except Exception:
            fecha = None
        if serial and model:
            rows.append(AccessRow(serial=serial, model=canonical_longfian_model(model), fecha_ingreso=fecha))
    cn.close()
    return rows


def build_serial_to_model(rows: List[AccessRow]) -> Dict[str, Tuple[str, Optional[str]]]:
    # Quedarnos con la entrada más reciente por serial normalizado
    seen: Dict[str, Tuple[str, Optional[str]]] = {}
    seen_time: Dict[str, str] = {}
    for r in rows:
        key = norm_key(r.serial)
        if not key:
            continue
        ts = r.fecha_ingreso or ""
        prev_ts = seen_time.get(key)
        if prev_ts is None or ts > prev_ts:
            seen[key] = (r.model, r.serial)
            seen_time[key] = ts
    return seen


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_model(cur, marca_id: int, model_name: str) -> int:
    cur.execute(
        "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
        (marca_id, model_name),
    )
    r = cur.fetchone()
    if r:
        return int(r[0])
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (marca_id, model_name))
    return int(cur.fetchone()[0])


def load_longfian_devices(cur, bid: int) -> Dict[str, Tuple[int, Optional[int], str]]:
    # key -> (device_id, model_id, raw_serial)
    cur.execute(
        "SELECT id, model_id, COALESCE(TRIM(numero_serie),'') FROM devices WHERE marca_id=%s",
        (bid,),
    )
    mapping: Dict[str, Tuple[int, Optional[int], str]] = {}
    for did, mid, serial in cur.fetchall() or []:
        raw = str(serial or "").strip()
        k = norm_key(raw)
        if not k:
            continue
        # Si hay duplicados con mismo serial, priorizamos mantener el primero; igual intentaremos actualizar ambos más adelante
        if k not in mapping:
            mapping[k] = (int(did), int(mid) if mid is not None else None, raw)
    return mapping


def model_name_by_id(cur) -> Dict[int, str]:
    cur.execute("SELECT id, nombre FROM models")
    return {int(r[0]): str(r[1]) for r in cur.fetchall() or []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica cambios en SR (por defecto: dry-run)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Leyendo Access (LONGFIAN)...")
    acc_rows = fetch_access_longfian()
    print(f"Registros LONGFIAN (Access): {len(acc_rows)}")
    serial_to_model = build_serial_to_model(acc_rows)
    print(f"Seriales únicos (Access): {len(serial_to_model)}")

    cn = connect_pg()
    if args.apply:
        cn.autocommit = False
    try:
        with cn.cursor() as cur:
            bid = brand_id(cur, "Longfian") or brand_id(cur, "LONGFIAN")
            if not bid:
                raise SystemExit("Marca 'Longfian' no encontrada en SR")
            dev_map = load_longfian_devices(cur, bid)
            mid2name = model_name_by_id(cur)

            planned: List[List[str]] = []
            updated_count = 0
            skipped_no_serial = 0
            ensured_models: Dict[str, int] = {}

            for skey, (canon_model, acc_serial) in serial_to_model.items():
                if skey not in dev_map:
                    continue
                device_id, cur_model_id, raw_serial = dev_map[skey]
                # asegurar modelo destino
                if canon_model not in ensured_models:
                    ensured_models[canon_model] = ensure_model(cur, bid, canon_model)
                dst_mid = ensured_models[canon_model]
                cur_name = mid2name.get(cur_model_id or -1, "")
                dst_name = canon_model
                if cur_model_id == dst_mid:
                    # ya correcto
                    continue
                planned.append([
                    str(device_id), raw_serial, cur_name, dst_name, acc_serial or "",
                ])
                if args.apply:
                    cur.execute("UPDATE devices SET model_id=%s WHERE id=%s", (dst_mid, device_id))
                    updated_count += 1

            # Guardar plan
            with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
                cw = csv.writer(f)
                cw.writerow(["device_id", "serial", "modelo_actual", "modelo_nuevo", "serial_access"])
                for row in planned:
                    cw.writerow(row)

            if args.apply:
                cn.commit()

            print("=== LONGFIAN desde Access ===")
            print(f"Plan de cambios: {OUT_CSV}")
            print(f"Devices con cambio planeado: {len(planned)}")
            if args.apply:
                print(f"Actualizados: {updated_count}")
            else:
                print("Modo: DRY-RUN (sin cambios en DB)")
    finally:
        try:
            cn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
