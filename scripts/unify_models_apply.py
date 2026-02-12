#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unifica modelos duplicados obvios dentro de la misma marca, preservando variantes
y catálogos (marca_tipos_equipo, marca_series, marca_series_variantes), sin
desasociar dispositivos.

Se basa en un mapeo (brand -> {target_model: [aliases...]}) derivado de los
duplicados detectados con scripts/list_model_duplicates.py.

Uso:
  POSTGRES_* por env (POSTGRES_HOST/PORT/DB/USER/PASSWORD)
  python scripts/unify_models_apply.py            # dry-run
  python scripts/unify_models_apply.py --apply    # aplica cambios
  python scripts/unify_models_apply.py --brand 'Philips Respironics'  # filtra
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Tuple

import psycopg  # type: ignore


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


# Mapeo de unificaciones por marca
PLAN: Dict[str, Dict[str, List[str]]] = {
    # Philips Respironics
    "Philips Respironics": {
        "CA-300": ["Ca 300"],
        "LA 651": ["La-651"],
        "REMSTAR N171": ["Remstar N 171"],
        "EVERFLO": ["Everflow"],
        "Millennium": ["Millenium"],
        "REMstar": ["Remstart", "REMSTAR"],
    },
    # Fisher & Paykel Healthcare
    "Fisher & Paykel Healthcare": {
        "HC150": ["HC 150"],
        "MR 428": ["MR428"],
    },
    # Nellcor
    "Nellcor": {
        "N-560": ["N 560", "N560"],
        "N-595": ["N 595", "N595"],
        "N-600X": ["N600x"],
        "NBP-295": ["Nbp 295"],
    },
    # Samtronic
    "Samtronic": {
        "ST-1000": ["St1000", "ST 1000"],
        "ST-1000 SET": ["St100 SET", "ST 100 SET", "ST-100 SET", "1000 SET"],
        "ST-550 T2": ["ST 550 T2"],
        "ST-6000": ["ST 6000"],
    },
    # Medix
    "Medix": {
        "OXI-3 PLUS": ["Oxi - 3 Plus"],
        "PC-305": ["Pc 305", "Pc305"],
    },
    # Newport
    "Newport": {
        "E-360": ["E 360", "E360"],
    },
    # EDAN
    "EDAN": {
        "SE-1": ["SE1"],
    },
    # EI
    "EI": {
        "K-130": ["K 130"],
    },
    # Fiorino
    "Fiorino": {
        "7 E-D": ["7ed"],
    },
    # Hoffrichter
    "Hoffrichter": {
        "CARAT 2": ["CARAT2"],
    },
    # Kairos
    "Kairos": {
        "MX 1": ["MX1"],
    },
    # Konsung
    "Konsung": {
        "9E-B": ["9EB"],
    },
    # Marbel
    "Marbel": {
        "C-500": ["C500"],
        "C-500-A": ["C500A"],
    },
    # Puritan Bennett
    "Puritan Bennett": {
        "420 E": ["420e"],
    },
    # ResMed
    "ResMed": {
        "S9": ["S-9"],
        "AirSense 10": ["AIR SENSE"],
    },
    # Schiller
    "Schiller": {
        "AT-1": ["AT1"],
    },
    # Sechrist Industries
    "Sechrist Industries": {
        "IV 100": ["Iv100"],
    },
    # Silfab
    "Silfab": {
        "N-33A": ["N33-A", "N33A", "N 33A", "N-33 A"],
        "N-33V": ["N33V", "N 33V", "N-33 V", "N 33 V"],
        "N-35A": ["N35A", "N 35A", "N-35 A"],
    },
    # Neumovent (Tecme)
    "Neumovent": {
        "GraphNet": ["Graph Net", "GRAHPNET", "GRAF", "Graph"],
        "TS": ["TS TECNO"],
        "Advance": ["ADVANCE"],
    },
    # Covidien (Kangaroo)
    "Covidien": {
        "Kangaroo ePump": ["EPUMP", "E PUMP", "ePUMP", "KANGAROO EPUMP", "KANGAROO E-PUMP"],
        "Kangaroo 224": ["224"],
        "Kangaroo 324": ["324"],
        "Kangaroo 924": ["924"],
    },
}


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def model_row(cur, marca_id: int, nombre: str) -> Optional[Tuple[int, str, str]]:
    cur.execute(
        "SELECT id, COALESCE(TRIM(tipo_equipo),''), COALESCE(TRIM(variante),'') FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, nombre),
    )
    r = cur.fetchone()
    return (int(r[0]), str(r[1]), str(r[2])) if r else None


def ensure_model(cur, marca_id: int, nombre: str) -> int:
    mr = model_row(cur, marca_id, nombre)
    if mr:
        return mr[0]
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (marca_id, nombre))
    return int(cur.fetchone()[0])


def ensure_catalog_for_series(cur, marca_id: int, tipo_txt: str, serie_nombre: str) -> Tuple[Optional[int], Optional[int]]:
    if not tipo_txt or not serie_nombre:
        return None, None
    # tipo (case-insensitive)
    cur.execute(
        "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_txt),
    )
    r = cur.fetchone()
    if not r:
        # insertar si no existe; si hay colisión por índice case-insensitive, ignorar
        try:
            cur.execute(
                "INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,TRUE)",
                (marca_id, tipo_txt),
            )
        except Exception:
            pass
        cur.execute(
            "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            (marca_id, tipo_txt),
        )
        r = cur.fetchone()
    tipo_id = int(r[0]) if r else None
    if not tipo_id:
        return None, None
    # serie
    cur.execute(
        "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_id, serie_nombre),
    )
    r2 = cur.fetchone()
    if not r2:
        cur.execute(
            "INSERT INTO marca_series(marca_id, tipo_id, nombre, activo) VALUES (%s,%s,%s,TRUE)",
            (marca_id, tipo_id, serie_nombre),
        )
    cur.execute(
        "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, tipo_id, serie_nombre),
    )
    r = cur.fetchone()
    serie_id = int(r[0]) if r else None
    return tipo_id, serie_id


def copy_catalog_variants(cur, marca_id: int, src_tipo_txt: str, src_serie_nombre: str, dst_tipo_id: int, dst_serie_id: int):
    if not src_tipo_txt or not src_serie_nombre:
        return
    cur.execute(
        "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, src_tipo_txt),
    )
    r = cur.fetchone()
    if not r:
        return
    src_tipo_id = int(r[0])
    cur.execute(
        "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
        (marca_id, src_tipo_id, src_serie_nombre),
    )
    r = cur.fetchone()
    if not r:
        return
    src_serie_id = int(r[0])
    cur.execute(
        "SELECT nombre FROM marca_series_variantes WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s",
        (marca_id, src_tipo_id, src_serie_id),
    )
    for (vname,) in cur.fetchall() or []:
        v = (vname or "").strip()
        if not v:
            continue
        cur.execute(
            "SELECT 1 FROM marca_series_variantes WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            (marca_id, dst_tipo_id, dst_serie_id, v),
        )
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo) VALUES (%s,%s,%s,%s,TRUE)",
                (marca_id, dst_tipo_id, dst_serie_id, v),
            )


def unify_one(cur, brand: str, target_model: str, alias_model: str, *, logs: List[str]):
    bid = brand_id(cur, brand)
    if not bid:
        logs.append(f"WARN: marca no encontrada: {brand}")
        return
    dst = model_row(cur, bid, target_model)
    src = model_row(cur, bid, alias_model)
    if not src:
        logs.append(f"INFO: alias no encontrado en '{brand}': {alias_model}")
        return
    # Si falta el destino, renombrar el src al nombre destino
    if not dst:
        cur.execute("UPDATE models SET nombre=%s WHERE id=%s", (target_model, src[0]))
        logs.append(f"rename: {brand} '{alias_model}' -> '{target_model}' (id={src[0]})")
        return

    src_id, src_tipo, src_var = int(src[0]), (src[1] or ""), (src[2] or "")
    dst_id, dst_tipo, dst_var = int(dst[0]), (dst[1] or ""), (dst[2] or "")

    # Reasignar devices al destino
    cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (dst_id, src_id))

    # Variante simple: completar en destino si falta
    if src_var and not dst_var:
        cur.execute("UPDATE models SET variante=%s WHERE id=%s", (src_var, dst_id))

    # Asegurar catálogo de serie y copiar variantes de la serie
    eff_tipo = dst_tipo or src_tipo
    tipo_id, serie_id = ensure_catalog_for_series(cur, bid, eff_tipo, target_model)
    if tipo_id and serie_id:
        # agregar var simples de ambos
        for v in [src_var, dst_var]:
            vv = (v or "").strip()
            if vv:
                cur.execute(
                    "SELECT 1 FROM marca_series_variantes WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    (bid, tipo_id, serie_id, vv),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo) VALUES (%s,%s,%s,%s,TRUE)",
                        (bid, tipo_id, serie_id, vv),
                    )
        copy_catalog_variants(cur, bid, src_tipo, alias_model, tipo_id, serie_id)

    # Eliminar modelo alias
    cur.execute("DELETE FROM models WHERE id=%s", (src_id,))
    logs.append(f"merge: {brand} '{alias_model}' -> '{target_model}' (dst_id={dst_id})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Aplica cambios (por defecto dry-run)")
    ap.add_argument("--brand", help="Filtrar por marca a procesar")
    args = ap.parse_args()

    logs: List[str] = []
    cn = connect_pg()
    try:
        if args.apply:
            cn.autocommit = False
        with cn.cursor() as cur:
            for brand, targets in PLAN.items():
                if args.brand and brand != args.brand:
                    continue
                for target_name, aliases in targets.items():
                    for alias in aliases:
                        unify_one(cur, brand, target_name, alias, logs=logs)
            if args.apply:
                cn.commit()
            else:
                cn.rollback()
    finally:
        try:
            cn.close()
        except Exception:
            pass

    print("=== Unificación de modelos (intra-marca) ===")
    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("-- Logs --")
    for line in logs:
        print(" *", line)


if __name__ == "__main__":
    main()
