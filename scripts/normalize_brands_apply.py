#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aplicar normalización de marcas y modelos en Postgres según mapeo provisto.

Acciones soportadas por marca origen:
- rename: Renombra a un nombre canónico (si existe otro registro con el nombre destino, fusiona)
- merge: Fusiona alias a marca canónica
- move_to_model: Convierte la 'marca' origen en un modelo dentro de una marca destino
- delete: Elimina la marca (anulando referencias en devices y borrando modelos asociados)
- keep: No hace nada (se listan en resumen)

Uso:
  POSTGRES_* por env (POSTGRES_HOST/PORT/DB/USER/PASSWORD)
  python scripts/normalize_brands_apply.py --apply

Por defecto corre en dry-run; con --apply confirma los cambios.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
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


def norm_key(s: str) -> str:
    return "".join(ch for ch in (s or "").strip().upper() if ch.isalnum())


@dataclass
class Action:
    kind: str  # rename | merge | move_to_model | delete | keep
    target_brand: Optional[str] = None
    target_model: Optional[str] = None


# Mapeo de acciones por nombre EXACTO como figura hoy en la tabla marcas.nombre
MAP: Dict[str, Action] = {
    # Eliminar
    "420": Action("delete"),
    "ALLIANCE": Action("delete"),
    "Apema": Action("delete"),
    "FINGER": Action("delete"),
    "MONITOR": Action("delete"),
    "NEONATAL": Action("delete"),
    "PORTATIL": Action("delete"),
    "REUSABLE": Action("delete"),
    "VACUM": Action("delete"),
    "VACUUM": Action("delete"),
    "led": Action("delete"),
    "Demobrand": Action("delete"),

    # Renombrar / Fusionar (merge si ya existe destino)
    "ABBOTT": Action("rename", target_brand="Abbott"),
    "Agilent": Action("rename", target_brand="Agilent Technologies"),
    "AIRSEP": Action("rename", target_brand="AirSep"),
    "AITEC": Action("rename", target_brand="Aitecs"),
    "Arcomed": Action("rename", target_brand="Arcomed AG"),
    "BIOCARE": Action("rename", target_brand="Biocare"),
    "BMD": Action("rename", target_brand="BMC"),
    "Breas": Action("rename", target_brand="Breas Medical"),
    "COVIDIEN": Action("rename", target_brand="Covidien"),
    "CAS": Action("rename", target_brand="CAS Medical Systems"),
    "Choice": Action("rename", target_brand="ChoiceMMed"),
    "Contec": Action("rename", target_brand="CONTEC"),
    "CARDIOTECNICA": Action("rename", target_brand="Cardiotécnica"),
    "Datex": Action("rename", target_brand="Datex-Ohmeda"),
    "DeVilbiss": Action("rename", target_brand="Drive DeVilbiss Healthcare"),
    "Easote": Action("rename", target_brand="Esaote"),
    "Edan": Action("rename", target_brand="EDAN"),
    "ELECTROMEDIC": Action("rename", target_brand="Electromedik"),
    "ELECTRO MEDICINA ARGENTINA": Action("rename", target_brand="Electromedicina Argentina"),
    "EMERSON": Action("rename", target_brand="Emerson"),
    "ENMIND": Action("rename", target_brand="Enmind"),
    "FEAS ELECTRONICA": Action("rename", target_brand="FEAS Electrónica"),
    "Fisher & Paykel": Action("rename", target_brand="Fisher & Paykel Healthcare"),
    "Fukuda": Action("rename", target_brand="Fukuda Denshi"),
    "General Electric": Action("rename", target_brand="GE Healthcare"),
    "HEALTHDYNE": Action("rename", target_brand="Healthdyne"),
    "Hewlett Packard": Action("rename", target_brand="Hewlett-Packard"),
    "HP": Action("rename", target_brand="Hewlett-Packard"),
    "HOFFRICHTER": Action("rename", target_brand="Hoffrichter"),
    "HYPNUS": Action("rename", target_brand="Hypnus"),
    "Innomed": Action("rename", target_brand="Innomed Medical"),
    "INOGEN": Action("rename", target_brand="Inogen"),
    "Kendall": Action("rename", target_brand="Kendall"),
    "Konsung": Action("rename", target_brand="Konsung"),
    "Laerdal": Action("rename", target_brand="Laerdal"),
    "LEEX": Action("rename", target_brand="LEEX"),
    "Leistung": Action("rename", target_brand="Leistung"),
    "LICFAMA": Action("rename", target_brand="LICFAMA"),
    "LONGFIAN": Action("rename", target_brand="Longfian"),
    "LOWENSTEIN": Action("rename", target_brand="Löwenstein Medical"),
    "MAGNAMED": Action("rename", target_brand="Magnamed"),
    "MARQUETTE": Action("rename", target_brand="Marquette"),
    "Masimo": Action("rename", target_brand="Masimo"),
    "MASSIMO": Action("rename", target_brand="Masimo"),
    "Maxtec": Action("rename", target_brand="Maxtec"),
    "Meditech": Action("rename", target_brand="Meditech"),
    "Medix": Action("rename", target_brand="Medix"),
    "Mindray": Action("rename", target_brand="Mindray"),
    "Movi-vac": Action("rename", target_brand="Movi-vac"),
    "MRL": Action("rename", target_brand="MRL"),
    "NELLCO R": Action("rename", target_brand="Nellcor"),  # defensivo por si existe typo
    "NELLCOR": Action("rename", target_brand="Nellcor"),
    "Neumovent": Action("rename", target_brand="Neumovent"),
    "Newport": Action("rename", target_brand="Newport"),
    "Nidek": Action("rename", target_brand="Nidek Medical"),
    "Novametrix": Action("rename", target_brand="Novametrix"),
    "Ohmeda": Action("rename", target_brand="Datex-Ohmeda"),
    "Phillips": Action("rename", target_brand="Philips"),
    "Phisyo Control": Action("rename", target_brand="Physio-Control"),
    "PRECISION MEDICAL": Action("rename", target_brand="Precision Medical"),
    "Pulmonetic": Action("rename", target_brand="Pulmonetic Systems"),
    "PURITAN BENNETT": Action("rename", target_brand="Puritan Bennett"),
    "RESMED": Action("rename", target_brand="ResMed"),
    "Respironics": Action("rename", target_brand="Philips Respironics"),
    "Samtronic": Action("rename", target_brand="Samtronic"),
    "Schiller": Action("rename", target_brand="Schiller"),
    "Sechrist": Action("rename", target_brand="Sechrist Industries"),
    "Silfab": Action("rename", target_brand="Silfab"),
    "Sunrise": Action("rename", target_brand="Sunrise Medical"),
    "Systel Vita": Action("rename", target_brand="Systel Vita"),
    "Taema": Action("rename", target_brand="Air Liquide Medical Systems"),
    "Valeylab": Action("rename", target_brand="Valleylab"),
    "Viasys": Action("rename", target_brand="Viasys Healthcare"),
    "WELCH ALLYN": Action("rename", target_brand="Welch Allyn"),
    "YAMIND": Action("rename", target_brand="Yamind"),
    "YUWELL": Action("rename", target_brand="Yuwell"),

    # Fusionar alias múltiples (se usa rename/merge según exista destino)
    "E&M": Action("rename", target_brand="Electromedicina Argentina"),
    "EM": Action("rename", target_brand="Electromedicina Argentina"),
    "EMA": Action("rename", target_brand="Electromedicina Argentina"),
    "WEINMANN": Action("rename", target_brand="Löwenstein Medical"),
    "VYASSIS": Action("rename", target_brand="Viasys Healthcare"),

    # Mover a MODELO: Marca -> (Marca destino · Modelo)
    "Cardimax": Action("move_to_model", target_brand="Fukuda Denshi", target_model="Cardimax"),
    "Code Master": Action("move_to_model", target_brand="Philips", target_model="CodeMaster"),
    "COMPANION": Action("move_to_model", target_brand="CAIRE", target_model="Companion 5"),
    "Compat": Action("move_to_model", target_brand="Nestlé Health Science", target_model="Compat"),
    "ISLEEP": Action("move_to_model", target_brand="Breas Medical", target_model="iSleep"),
    "JAY": Action("move_to_model", target_brand="Longfian", target_model="JAY-5"),
    "Kangaroo": Action("move_to_model", target_brand="Covidien", target_model="Kangaroo"),
    "HARMONY": Action("move_to_model", target_brand="ResMed", target_model="Harmony"),
    "HC-150": Action("move_to_model", target_brand="Fisher & Paykel Healthcare", target_model="HC150"),
    "EAGLE": Action("move_to_model", target_brand="Marquette", target_model="Eagle"),
    "Everflo": Action("move_to_model", target_brand="Philips Respironics", target_model="EverFlo"),
    "GOOD KINGHT": Action("move_to_model", target_brand="Puritan Bennett", target_model="GoodKnight"),
    "GOODKNIGHT": Action("move_to_model", target_brand="Puritan Bennett", target_model="GoodKnight"),
    "MILLENIUM": Action("move_to_model", target_brand="CAIRE", target_model="Millennium"),
    "NATALCARE": Action("move_to_model", target_brand="Huntleigh", target_model="NatalCare"),
    "OXIMAX": Action("move_to_model", target_brand="Nellcor", target_model="OxiMax"),
    "REMSTART": Action("move_to_model", target_brand="Philips Respironics", target_model="REMstar"),
    "Resmart": Action("move_to_model", target_brand="BMC", target_model="RESmart"),
    "S9": Action("move_to_model", target_brand="ResMed", target_model="S9"),
    "Samaritan": Action("move_to_model", target_brand="HeartSine", target_model="samaritan"),
    "SERIE M": Action("move_to_model", target_brand="ZOLL", target_model="M-Series"),
    "TANGO": Action("move_to_model", target_brand="SunTech Medical", target_model="Tango"),
    "TRANSCEND": Action("move_to_model", target_brand="Somnetics", target_model="Transcend"),
    "Vacumax": Action("move_to_model", target_brand="Drive DeVilbiss Healthcare", target_model="Vacumax"),
    "Vision Aire": Action("move_to_model", target_brand="AirSep", target_model="VisionAire"),
    "Volumed": Action("move_to_model", target_brand="Arcomed AG", target_model="Volumed"),
    "CAIRE OCS Y COMPANION 5": Action("rename", target_brand="CAIRE"),
}


# Conjunto de marcas a NO tocar (revisión manual)
REVIEW: List[str] = [
    "ALISON", "BMG", "BMP", "BMXC", "BS ELECTRONICS", "CAM", "Cloud", "Corionik",
    "Dulovak", "EI", "Fiorino", "Kairos", "Life Care", "LIFE PORT", "Marbel",
    "Medd", "Medical Healthy", "MEK", "MERCURY", "MVP-10", "ORION", "OXI-3",
    "Patrol", "POINT", "QUAMTUM", "Razel", "Remedy", "REMEDY RENEW", "Respire",
    "Rhomicron", "Rosch", "SATLITE", "SEGALINI", "Tranquility", "Tronik", "Weros",
]


def fetch_brand_row(cur, name: str) -> Optional[Tuple[int, str]]:
    cur.execute("SELECT id, nombre FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (name,))
    r = cur.fetchone()
    return (int(r[0]), str(r[1])) if r else None


def fetch_brand_id_by_name(cur, name: str) -> Optional[int]:
    r = fetch_brand_row(cur, name)
    return r[0] if r else None


def ensure_brand(cur, name: str) -> int:
    rid = fetch_brand_id_by_name(cur, name)
    if rid is not None:
        return rid
    cur.execute("INSERT INTO marcas(nombre) VALUES (%s) RETURNING id", (name,))
    return int(cur.fetchone()[0])


def list_models_by_brand(cur, brand_id: int) -> List[Tuple[int, str]]:
    cur.execute("SELECT id, nombre FROM models WHERE marca_id=%s", (brand_id,))
    return [(int(r[0]), str(r[1])) for r in cur.fetchall()]


def find_model_id(cur, brand_id: int, model_name: str) -> Optional[int]:
    cur.execute(
        "SELECT id FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
        (brand_id, model_name),
    )
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_model(cur, brand_id: int, model_name: str) -> int:
    mid = find_model_id(cur, brand_id, model_name)
    if mid is not None:
        return mid
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (brand_id, model_name))
    return int(cur.fetchone()[0])


def merge_brands_ids(cur, src_id: int, dst_id: int, *, logs: List[str]):
    if src_id == dst_id:
        return
    # Unificar modelos
    cur.execute("SELECT id, nombre FROM models WHERE marca_id=%s", (src_id,))
    src_models = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
    cur.execute("SELECT id, nombre FROM models WHERE marca_id=%s", (dst_id,))
    dst_models = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
    dst_norm = {norm_key(n): (mid, n) for (mid, n) in dst_models}

    for smid, sname in src_models:
        key = norm_key(sname)
        if key in dst_norm:
            dmid, dname = dst_norm[key]
            # Reasignar devices -> modelo destino
            cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (dmid, smid))
            cur.execute("DELETE FROM models WHERE id=%s", (smid,))
            logs.append(f"models: merge '{sname}' -> '{dname}' (dst_id={dmid})")
        else:
            # Mover el modelo a la marca destino
            cur.execute("UPDATE models SET marca_id=%s WHERE id=%s", (dst_id, smid))
            logs.append(f"models: move '{sname}' -> brand_id={dst_id}")

    # Reasignar devices de la marca
    cur.execute("UPDATE devices SET marca_id=%s WHERE marca_id=%s", (dst_id, src_id))
    # Eliminar marca origen
    cur.execute("DELETE FROM marcas WHERE id=%s", (src_id,))


def rename_or_merge_brand(cur, src_name: str, dst_name: str, *, logs: List[str]):
    src = fetch_brand_row(cur, src_name)
    if not src:
        logs.append(f"WARN: marca origen no encontrada para renombrar: '{src_name}'")
        return
    src_id, real_src_name = src
    dst = fetch_brand_row(cur, dst_name)
    if not dst:
        # Renombrar in-situ
        cur.execute("UPDATE marcas SET nombre=%s WHERE id=%s", (dst_name, src_id))
        logs.append(f"marca: rename '{real_src_name}' -> '{dst_name}' (id={src_id})")
        return
    dst_id, real_dst_name = dst
    if dst_id == src_id:
        if real_dst_name != dst_name:
            # Mismo registro (case/acentos distintos): actualizar nombre exacto destino
            cur.execute("UPDATE marcas SET nombre=%s WHERE id=%s", (dst_name, src_id))
            logs.append(f"marca: rename-case '{real_dst_name}' -> '{dst_name}' (id={src_id})")
        else:
            logs.append(f"marca: ok '{dst_name}' ya normalizada (id={dst_id})")
        return
    # Fusionar src -> dst (ids distintos)
    merge_brands_ids(cur, src_id, dst_id, logs=logs)
    logs.append(f"marca: merge '{real_src_name}' -> '{real_dst_name}' (dst_id={dst_id})")


def delete_brand(cur, brand_name: str, *, logs: List[str]):
    row = fetch_brand_row(cur, brand_name)
    if not row:
        logs.append(f"INFO: marca a eliminar no encontrada: '{brand_name}' (skip)")
        return
    bid, real = row
    # Devices: limpiar model_id donde apunte a modelos de esta marca
    cur.execute("SELECT id FROM models WHERE marca_id=%s", (bid,))
    mids = [int(r[0]) for r in cur.fetchall()]
    if mids:
        cur.execute("UPDATE devices SET model_id=NULL WHERE model_id = ANY(%s)", (mids,))
        # Eliminar modelos
        cur.execute("DELETE FROM models WHERE id = ANY(%s)", (mids,))
        logs.append(f"models: delete {len(mids)} en marca '{real}'")
    # Devices: limpiar marca
    cur.execute("UPDATE devices SET marca_id=NULL WHERE marca_id=%s", (bid,))
    # Eliminar marca
    cur.execute("DELETE FROM marcas WHERE id=%s", (bid,))
    logs.append(f"marca: delete '{real}' (id={bid})")


def move_brand_to_model(cur, src_brand: str, dst_brand: str, model_name: str, *, logs: List[str]):
    src = fetch_brand_row(cur, src_brand)
    if not src:
        logs.append(f"WARN: marca para mover no encontrada: '{src_brand}'")
        return
    src_id, real_src = src
    dst_id = ensure_brand(cur, dst_brand)
    model_id = ensure_model(cur, dst_id, model_name)

    # Para todos los modelos de la marca origen: dispositivos -> model_id destino, borrar modelos
    cur.execute("SELECT id, nombre FROM models WHERE marca_id=%s", (src_id,))
    src_models = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
    for smid, sname in src_models:
        cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (model_id, smid))
        cur.execute("DELETE FROM models WHERE id=%s", (smid,))
        logs.append(f"models: collapse '{sname}' -> '{model_name}' (dst_model_id={model_id})")

    # Devices con marca origen pero model_id NULL -> asignar modelo destino
    cur.execute("UPDATE devices SET model_id=%s WHERE marca_id=%s AND (model_id IS NULL)", (model_id, src_id))
    # Reasignar marca en devices
    cur.execute("UPDATE devices SET marca_id=%s WHERE marca_id=%s", (dst_id, src_id))
    # Eliminar marca origen
    cur.execute("DELETE FROM marcas WHERE id=%s", (src_id,))
    logs.append(f"marca: move-as-model '{real_src}' -> '{dst_brand} · {model_name}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Ejecuta cambios (por defecto: dry-run)")
    ap.add_argument("--only", nargs="*", help="Procesar solo estas marcas (nombre exacto como hoy en DB)")
    args = ap.parse_args()

    only_set = {o.strip() for o in (args.only or []) if o and o.strip()}

    logs: List[str] = []
    keeplist: List[str] = []
    review_list: List[str] = list(REVIEW)
    missing: List[str] = []

    cn = connect_pg()
    with cn:
        with cn.cursor() as cur:
            if not args.apply:
                cur.execute("BEGIN")
                cur.execute("SET TRANSACTION READ WRITE")
            # 1) Renames / merges (incluye alias)
            for src, action in MAP.items():
                if only_set and src not in only_set:
                    continue
                if action.kind == "rename":
                    rename_or_merge_brand(cur, src, action.target_brand or src, logs=logs)
                elif action.kind == "merge":
                    rename_or_merge_brand(cur, src, action.target_brand or src, logs=logs)
                elif action.kind == "delete":
                    delete_brand(cur, src, logs=logs)
                elif action.kind == "move_to_model":
                    move_brand_to_model(cur, src, action.target_brand or src, action.target_model or src, logs=logs)
                elif action.kind == "keep":
                    keeplist.append(src)

            # 2) Reportar marcas de revisión que existan actualmente
            for name in review_list:
                cur.execute("SELECT 1 FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (name,))
                if not cur.fetchone():
                    missing.append(name)

            if not args.apply:
                # rollback implícito saliendo del bloque; pero explicitamos
                cn.rollback()

    print("=== Normalización de marcas/modelos ===")
    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("-- Logs --")
    for line in logs:
        print(" *", line)
    print("-- Revisar manualmente (sin cambios) --")
    for name in review_list:
        print(" -", name)
    if missing:
        print("-- No encontradas (revisión): --")
        for name in missing:
            print(" -", name)


if __name__ == "__main__":
    main()
