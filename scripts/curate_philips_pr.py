#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Curado de modelos para Philips y Philips Respironics según reglas funcionales:

- Philips = monitores y desfibriladores (Viridia V24/V24C/M3/M4, CodeMaster).
- Philips Respironics = CPAP/BPAP, EverFlo/Millennium, POC SimplyGo, REMstar/System One/C-Series.

Acciones:
- Mover modelos entre marcas cuando corresponden (p.ej., AVAPS -> Philips Respironics)
- Renombrar modelos a su forma canónica
- Ajustar tipo_equipo (CPAP/BPAP/MONITOR/DESFIBRILADOR/POC/etc.)
- Unificar alias frecuentes y limpiar entradas no-modelo cuando es seguro

Uso:
  POSTGRES_* por env
  python scripts/curate_philips_pr.py            # dry-run
  python scripts/curate_philips_pr.py --apply    # aplicar cambios
"""

from __future__ import annotations

import argparse
import os
from typing import Optional, Tuple, List

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


def brand_id(cur, name: str) -> Optional[int]:
    cur.execute("SELECT id FROM marcas WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (name,))
    r = cur.fetchone()
    return int(r[0]) if r else None


def ensure_brand(cur, name: str) -> int:
    bid = brand_id(cur, name)
    if bid is not None:
        return bid
    cur.execute("INSERT INTO marcas(nombre) VALUES (%s) RETURNING id", (name,))
    return int(cur.fetchone()[0])


def model_row(cur, brand_id: int, name: str) -> Optional[Tuple[int, str, str]]:
    cur.execute(
        "SELECT id, COALESCE(TRIM(tipo_equipo),''), COALESCE(TRIM(variante),'') FROM models WHERE marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1",
        (brand_id, name),
    )
    r = cur.fetchone()
    return (int(r[0]), str(r[1]), str(r[2])) if r else None


def find_any_model(cur, brand_id: int, names: List[str]) -> Optional[Tuple[int, str, str, str]]:
    for n in names:
        r = model_row(cur, brand_id, n)
        if r:
            return (r[0], n, r[1], r[2])
    return None


def ensure_model(cur, brand_id: int, name: str) -> int:
    r = model_row(cur, brand_id, name)
    if r:
        return int(r[0])
    cur.execute("INSERT INTO models(marca_id, nombre) VALUES (%s,%s) RETURNING id", (brand_id, name))
    return int(cur.fetchone()[0])


def set_model_name_and_type(cur, model_id: int, new_name: Optional[str] = None, tipo: Optional[str] = None):
    if new_name and tipo:
        cur.execute("UPDATE models SET nombre=%s, tipo_equipo=%s WHERE id=%s", (new_name, tipo, model_id))
    elif new_name:
        cur.execute("UPDATE models SET nombre=%s WHERE id=%s", (new_name, model_id))
    elif tipo:
        cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, model_id))


def merge_or_move_model(cur, src_brand: str, model_aliases: List[str], dst_brand: str, dst_model_name: str, tipo: Optional[str], logs: List[str]):
    a = brand_id(cur, src_brand)
    if not a:
        logs.append(f"WARN: marca origen no existe: {src_brand}")
        return
    b = ensure_brand(cur, dst_brand)

    src = find_any_model(cur, a, model_aliases)
    if not src:
        logs.append(f"INFO: modelo no encontrado en '{src_brand}': {model_aliases}")
        return
    src_id, found_name, src_tipo, src_var = src

    # Intentar encontrar un modelo destino existente ya sea por nombre objetivo o por algún alias
    dst = model_row(cur, b, dst_model_name)
    if not dst:
        for alt in [found_name] + [n for n in model_aliases if n != found_name]:
            dst = model_row(cur, b, alt)
            if dst:
                break

    if dst:
        dst_id = int(dst[0])
        # Asegurar nombre canónico en destino si difiere
        cur.execute("SELECT UPPER(TRIM(nombre)) FROM models WHERE id=%s", (dst_id,))
        current_name = (cur.fetchone() or [""])[0]
        if current_name != dst_model_name.upper().strip():
            # ¿Existe otro con el nombre objetivo? si no, renombrar destino
            clash = model_row(cur, b, dst_model_name)
            if not clash:
                set_model_name_and_type(cur, dst_id, dst_model_name, None)
        # Reasignar devices al destino y borrar origen
        cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (dst_id, src_id))
        cur.execute("DELETE FROM models WHERE id=%s", (src_id,))
        # opcional: set tipo_equipo
        if tipo:
            cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, dst_id))
        # Asegurar marca_id en devices
        cur.execute("UPDATE devices SET marca_id=%s WHERE model_id=%s", (b, dst_id))
        logs.append(f"merge-move: {src_brand} '{found_name}' -> {dst_brand} '{dst_model_name}'")
        return

    # Renombrar primero en la marca origen para evitar colisiones, luego mover
    set_model_name_and_type(cur, src_id, dst_model_name, tipo)
    cur.execute("UPDATE models SET marca_id=%s WHERE id=%s", (b, src_id))
    cur.execute("UPDATE devices SET marca_id=%s WHERE model_id=%s", (b, src_id))
    logs.append(f"move: {src_brand} '{found_name}' -> {dst_brand} '{dst_model_name}'")


def rename_model_in_brand(cur, brand: str, aliases: List[str], new_name: str, tipo: Optional[str], logs: List[str]):
    bid = brand_id(cur, brand)
    if not bid:
        logs.append(f"WARN: marca no existe: {brand}")
        return
    src = find_any_model(cur, bid, aliases)
    if not src:
        logs.append(f"INFO: modelo no encontrado en '{brand}': {aliases}")
        return
    mid, found_name, _, _ = src
    # ¿Existe homónimo con new_name?
    dst = model_row(cur, bid, new_name)
    if dst and dst[0] != mid:
        dst_id = int(dst[0])
        # devices -> dst y borrar src
        cur.execute("UPDATE devices SET model_id=%s WHERE model_id=%s", (dst_id, mid))
        cur.execute("DELETE FROM models WHERE id=%s", (mid,))
        if tipo and not (dst[1] or "").strip():
            cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo, dst_id))
        logs.append(f"merge: {brand} '{found_name}' -> '{new_name}'")
        return
    set_model_name_and_type(cur, mid, new_name, tipo)
    logs.append(f"rename: {brand} '{found_name}' -> '{new_name}'")


def drop_non_model_to_brand(cur, brand_from: str, model_name: str, brand_to: str, logs: List[str]):
    a = brand_id(cur, brand_from)
    if not a:
        return
    src = model_row(cur, a, model_name)
    if not src:
        return
    mid = int(src[0])
    b = ensure_brand(cur, brand_to)
    # Devices pasan a la marca destino con model_id NULL
    cur.execute("UPDATE devices SET marca_id=%s, model_id=NULL WHERE model_id=%s", (b, mid))
    cur.execute("DELETE FROM models WHERE id=%s", (mid,))
    logs.append(f"drop-nonmodel: '{brand_from}' modelo '{model_name}' -> marca '{brand_to}' (devices mantienen marca)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Aplica cambios (default: dry-run)')
    args = ap.parse_args()

    logs: List[str] = []
    cn = connect_pg()
    try:
        with cn:
            with cn.cursor() as cur:
                if not args.apply:
                    cur.execute('BEGIN')
                # Philips (monitores/desfibriladores)
                rename_model_in_brand(cur, 'Philips', ['24C'], 'Viridia V24C', 'MONITOR MULTIPARAMETRICO', logs)
                rename_model_in_brand(cur, 'Philips', ['V24'], 'Viridia V24', 'MONITOR MULTIPARAMETRICO', logs)
                rename_model_in_brand(cur, 'Philips', ['M3'], 'M3', 'MONITOR MULTIPARAMETRICO', logs)
                rename_model_in_brand(cur, 'Philips', ['M4'], 'M4', 'MONITOR MULTIPARAMETRICO', logs)
                rename_model_in_brand(cur, 'Philips', ['CodeMaster'], 'CodeMaster', 'DESFIBRILADOR', logs)

                # Mover a Philips Respironics
                merge_or_move_model(cur, 'Philips', ['AVAPS'], 'Philips Respironics', 'BiPAP AVAPS', 'BPAP', logs)
                merge_or_move_model(cur, 'Philips', ['C-SERIES', 'SERIE C'], 'Philips Respironics', 'C-Series (A30/A40)', 'BPAP', logs)
                merge_or_move_model(cur, 'Philips', ['PRO'], 'Philips Respironics', 'REMstar Pro', 'CPAP', logs)
                merge_or_move_model(cur, 'Philips', ['REMSTAR'], 'Philips Respironics', 'REMstar', 'CPAP', logs)
                merge_or_move_model(cur, 'Philips', ['SIMPLYGO'], 'Philips Respironics', 'SimplyGo', 'CONCENTRADOR DE OXIGENO PORTATIL', logs)
                merge_or_move_model(cur, 'Philips', ['SYSTEM ONE'], 'Philips Respironics', 'System One', 'CPAP/BPAP', logs)
                # RESPIRONICS como no-modelo
                drop_non_model_to_brand(cur, 'Philips', 'RESPIRONICS', 'Philips Respironics', logs)

                # Philips Respironics ajustes
                rename_model_in_brand(cur, 'Philips Respironics', ['DORMA', 'DORMA 100'], 'Dorma 100', 'CPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['AUTO SV'], 'BiPAP autoSV', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['AVAPS'], 'BiPAP AVAPS', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['BI-PAP PRO', 'PRO'], 'BiPAP Pro', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['BPAP ST', '425 ST'], 'BiPAP S/T 425', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['HARMONY'], 'BiPAP Harmony', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['LA 651', 'La651s'], 'LA651S', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['REMSTAR N171', 'N171', 'IN 171', '171'], 'REMstar SE 171P', 'CPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['450 P'], 'REMstar Pro 450P', 'CPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['EVERFLO', 'Everflow'], 'EVERFLO', 'CONCENTRADOR DE OXIGENO', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['EVER GO'], 'EverGo', 'CONCENTRADOR DE OXIGENO PORTATIL', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['PLUS', 'PLUS SERIE M'], 'REMstar Plus', 'CPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['SLEEP', 'SLEEP EASY'], 'SleepEasy', 'CPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['SYNCHRONY'], 'BiPAP Synchrony', 'BPAP', logs)
                rename_model_in_brand(cur, 'Philips Respironics', ['System ONE'], 'System One', 'CPAP/BPAP', logs)

                # NICO2 -> Philips (módulo)
                merge_or_move_model(cur, 'Philips Respironics', ['NICO2'], 'Philips', 'NICO2', 'MODULO CO2/CO', logs)

                # RESMART en Philips Respironics -> BMC RESmart
                merge_or_move_model(cur, 'Philips Respironics', ['RESMART', 'Resmart Serie M'], 'BMC', 'RESmart', None, logs)

                # RESMED modelo erróneo en PR -> mover a marca ResMed
                merge_or_move_model(cur, 'Philips Respironics', ['RESMED'], 'ResMed', 'S9', None, logs)

                # EMERSON como marca separada
                merge_or_move_model(cur, 'Philips Respironics', ['EMERSON'], 'Emerson', 'EMERSON', None, logs)

                if not args.apply:
                    cn.rollback()

    finally:
        try:
            cn.close()
        except Exception:
            pass

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f"=== Curado Philips/Philips Respironics ({mode}) ===")
    for l in logs:
        print(" *", l)


if __name__ == '__main__':
    main()
