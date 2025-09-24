#!/usr/bin/env python3
"""Normalize Marca/Modelo values in the Access Servicio table."""

import argparse
import csv
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

import pyodbc

DEFAULT_DB = Path(r"Z:\Servicio Tecnico\1_SISTEMA REPARACIONES\2025-06\Tablas2025 MG-SEPID 2.0.accdb")
BASE_THRESHOLD = 5
SIMILARITY_THRESHOLD = 0.8

BRAND_REPLACEMENTS: Dict[str, str] = {
    "": "",
    "AIRSEP": "AIRSEP",
    "LONGFIAN": "LONGFIAN",
    "MOCIVAC": "MOVI-VAC",
    "MOVIVAC": "MOVI-VAC",
    "RESPMED": "RESMED",
    "RESMED": "RESMED",
    "RESPIRONICS": "RESPIRONICS",
    "RESPIRONIC": "RESPIRONICS",
    "REPIRONIC": "RESPIRONICS",
    "RESRONIC": "RESPIRONICS",
    "RESPRONIC": "RESPIRONICS",
    "RESPIRONIS": "RESPIRONICS",
    "DEBILBISS": "DEVILBISS",
    "DEBILVIS": "DEVILBISS",
    "DEBILBIS": "DEVILBISS",
    "DEBILVISS": "DEVILBISS",
    "DEVILBIS": "DEVILBISS",
    "DEVILVIS": "DEVILBISS",
    "DEVILBIIS": "DEVILBISS",
    "DEVILBIISS": "DEVILBISS",
    "DEVILBBIS": "DEVILBISS",
    "DEVILDISS": "DEVILBISS",
    "DEVILVISS": "DEVILBISS",
    "DEVILLBIS": "DEVILBISS",
    "FICHERPAYKEL": "FISHER & PAYKEL",
    "FISHERPAYKEL": "FISHER & PAYKEL",
    "FISHERPAYKAL": "FISHER & PAYKEL",
    "FISHERPIKEL": "FISHER & PAYKEL",
    "FISHERYPAYKEL": "FISHER & PAYKEL",
    "FP": "FISHER & PAYKEL",
    "PURITABENNETT": "PURITAN BENNETT",
    "PURITANBENNET": "PURITAN BENNETT",
    "PURITANBENNETT": "PURITAN BENNETT",
    "PURITTANBENNET": "PURITAN BENNETT",
    "PURITTANBENNETT": "PURITAN BENNETT",
    "PURITAN&BENNET": "PURITAN BENNETT",
    "PB": "PURITAN BENNETT",
    "PBENNETT": "PURITAN BENNETT",
    "SAMTRONIC": "SAMTRONIC",
    "SAMTROIC": "SAMTRONIC",
    "SANTRONIC": "SAMTRONIC",
    "SAMTRONI": "SAMTRONIC",
    "SAMTRONC": "SAMTRONIC",
    "SAMRTONIC": "SAMTRONIC",
    "MASSIMO": "MASIMO",
    "MASIMO": "MASIMO",
    "YUWELL": "YUWELL",
    "YUWELLL": "YUWELL",
    "MABEL": "MARBEL",
    "MRBEL": "MARBEL",
    "ORYON": "ORION",
    "KANGROO": "KANGAROO",
    "KANGARO": "KANGAROO",
    "RESPRE": "RESPIRE",
    "PHILLIPS": "PHILIPS",
    "HPPHILIPS": "PHILIPS",
    "HEAHLDYNE": "HEALTHDYNE",
    "HEALTTDYNE": "HEALTHDYNE",
    "VACUM": "VACUUM",
    "VACUUM": "VACUUM",
    "NELLCOR": "NELLCOR",
    "NELCOR": "NELLCOR",
    "NLLCOR": "NELLCOR",
    "NELLCOR560": "NELLCOR",
    "NELLCORCONCURVA": "NELLCOR",
    "NELLCORPB": "NELLCOR",
    "NELLOR": "NELLCOR",
    "SMARCA": "SIN MARCA",
    "LNGFIAN": "LONGFIAN",
    "SAMTRONC": "SAMTRONIC",
}

MODEL_OVERRIDES: Dict[str, Dict[str, str]] = {
    "AIRSEP": {
        "INTENSITY10L": "INTENSITY 10L",
        "INTENSITY8L": "INTENSITY 8L",
        "MEWLIFE": "NEW LIFE",
        "NEWIFE": "NEW LIFE",
        "NEWLIFW": "NEW LIFE",
        "NEWLIFE5L": "NEW LIFE 5L",
        "NEWLIFEELITE": "NEW LIFE ELITE",
        "NRWNEW": "NEW LIFE",
        "INFINIT": "INFINITI",
        "VISIONAIRE": "VISIONAIRE",
    },
    "LONGFIAN": {
        "JAY5": "JAY-5",
        "JAY5Q": "JAY-5Q",
        "JAY10": "JAY-10",
        "JAY10D": "JAY-10D",
        "JAY120": "JAY-120",
        "JSB1200": "JSB-1200",
    },
    "MOVI-VAC": {
        "A550": "A-550",
        "A600": "A-600",
        "A220": "A-220",
        "A220V": "A-220V",
        "A55O": "A-550",
        "A500": "A-500",
        "A360": "A-360",
        "A10122": "A1-0122",
        "B40705": "B4-0705",
        "C500A": "C-500-A",
        "C550": "C-550",
        "MOVIVAC": "MOVI-VAC",
    },
    "BMC": {
        "POYLWATCH": "POLYWATCH",
        "POLYWACH": "POLYWATCH",
        "POLIPROA": "POLYPRO A",
        "POLYWATCHYH6000BPRO": "POLYWATCH YH-6000B PRO",
        "RESMARTAUTO": "RESMART AUTO",
        "RESMARTG1": "RESMART G1",
        "RESMARTG2": "RESMART G2",
        "RESMARTGII": "RESMART GII",
        "RESMARTG125T": "RESMART G1 25T",
        "RESMARTSERIEM": "RESMART SERIE M",
        "G2SA20": "G2S A20",
        "G2SB25S": "G2S B25S",
        "G2SB25T": "G2S B25T",
        "G2SB25A": "G2S B25A",
        "G2SB20V": "G2S B20V",
        "G2SC20": "G2S C20",
        "G2T25T": "G2 T25T",
        "G125": "G1 25",
        "G125S": "G1 25S",
        "G125T": "G1 25T",
        "GIIT25A": "GII T25A",
        "GIIT25S": "GII T25S",
        "GI25": "GI 25",
        "GI25T": "GI 25T",
        "G2Y25T": "G2 Y25T",
        "H80M": "H-80M",
        "H80A": "H-80A",
        "HG2H60": "HG2 H60",
        "25ST": "25ST",
        "MINI": "MINI",
        "M1MINI": "MINI M1",
        "POLYPRO": "POLYPRO",
    },
    "NELLCOR": {
        "N560": "N-560",
        "N395": "N-395",
        "N600": "N-600",
        "N600X": "N-600X",
        "N290": "N-290",
        "N550": "N-550",
        "NPB290": "NPB-290",
        "NPB4000": "NPB-4000",
        "NPB195": "NPB-195",
        "NBP295": "NBP-295",
        "N595": "N-595",
        "BEDISDE": "BEDSIDE",
    },
    "SILFAB": {
        "N33A": "N-33A",
        "N33V": "N-33V",
        "N35A": "N-35A",
    },
    "SAMTRONIC": {
        "ST1000SET": "ST-1000 SET",
        "ST6000": "ST-6000",
        "550T2": "ST-550 T2",
        "ST1000": "ST-1000",
        "ST7000": "ST-7000",
        "ST1000V40": "ST-1000 V4.0",
        "ST100040": "ST-1000 4.0",
        "1000SET": "ST-1000 SET",
        "1000": "ST-1000",
        "550": "ST-550",
        "ST1000E": "ST-1000 E",
        "ST550T2": "ST-550 T2",
    },
    "RESPIRONICS": {
        "SERIEM": "SERIE M",
        "SISTEMEONE": "SYSTEM ONE",
        "EVERFLOW": "EVERFLO",
        "MILENIUM": "MILLENIUM",
        "PHILIPS": "PHILIPS",
    },
    "RESMED": {
        "S9": "S9",
        "S9AUTO": "S9 AUTO",
        "S9ELITE": "S9 ELITE",
    },
}

def format_brand(name: str) -> str:
    if name is None:
        return ""
    return re.sub(r"\s+", " ", name.strip().upper())

def normalize_brand_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", format_brand(name))

def canonical_brand(name: str) -> str:
    norm = normalize_brand_key(name)
    if norm in BRAND_REPLACEMENTS:
        return BRAND_REPLACEMENTS[norm]
    return format_brand(name)

def format_model(name: str) -> str:
    if name is None:
        return ""
    text = re.sub(r"\s+", " ", name.strip().upper())
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*&\s*", "&", text)
    return text

def normalize_model_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", format_model(name))

def build_canonical_models(brand_variants: Dict[str, Dict[str, Counter]]) -> Tuple[Dict[str, Dict[str, str]], List[Tuple[str, str, int, str]]]:
    canonical: Dict[str, Dict[str, str]] = {}
    review: List[Tuple[str, str, int, str]] = []
    for brand, norm_map in brand_variants.items():
        totals = {norm: sum(counter.values()) for norm, counter in norm_map.items()}
        base_norms = {norm for norm, total in totals.items() if total >= BASE_THRESHOLD}
        overrides = MODEL_OVERRIDES.get(brand, {})
        base_norms.update(overrides.keys())
        brand_map: Dict[str, str] = {}
        for norm, counter in norm_map.items():
            top = counter.most_common(1)[0][0] if counter else ""
            value = format_model(top)
            if norm in overrides:
                value = overrides[norm]
            brand_map[norm] = value
        base_list = list(base_norms)
        for norm, total in totals.items():
            if norm in base_norms:
                continue
            if norm in overrides:
                brand_map[norm] = overrides[norm]
                continue
            best_ratio = 0.0
            best_norm = None
            for base_norm in base_list:
                if not base_norm:
                    continue
                ratio = SequenceMatcher(None, norm, base_norm).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_norm = base_norm
            if best_norm and best_ratio >= SIMILARITY_THRESHOLD:
                brand_map[norm] = brand_map[best_norm]
            else:
                top = norm_map[norm].most_common(1)[0][0] if norm_map[norm] else ""
                value = format_model(top)
                brand_map[norm] = value
                review.append((brand, norm, total, value))
        canonical[brand] = brand_map
    return canonical, review

def fetch_brand_model_counts(cursor) -> List[Tuple[str, str, int]]:
    cursor.execute("SELECT Marca, Modelo, COUNT(*) FROM Servicio GROUP BY Marca, Modelo")
    return [(row[0] or "", row[1] or "", row[2]) for row in cursor.fetchall()]

def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Servicio Marca/Modelo values")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Ruta al archivo .accdb")
    parser.add_argument("--apply", action="store_true", help="Ejecuta los UPDATE en la base")
    parser.add_argument("--preview-csv", type=Path, default=Path("tmp/brand_model_updates_preview.csv"), help="Ruta a CSV de vista previa")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"No se encontró la base de datos: {args.db}")

    conn = pyodbc.connect(rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={args.db};")
    conn.autocommit = False
    cursor = conn.cursor()

    combos = fetch_brand_model_counts(cursor)
    brand_variants: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for marca, modelo, qty in combos:
        canon_brand = canonical_brand(marca)
        norm_model = normalize_model_key(modelo)
        formatted_model = format_model(modelo)
        brand_variants[canon_brand][norm_model][formatted_model] += qty

    canonical_models, review = build_canonical_models(brand_variants)

    updates: List[Tuple[str, str, str, str, int]] = []
    for marca, modelo, qty in combos:
        canon_brand = canonical_brand(marca)
        norm_model = normalize_model_key(modelo)
        canon_model = canonical_models.get(canon_brand, {}).get(norm_model, format_model(modelo))
        if canon_brand != marca or canon_model != modelo:
            updates.append((marca, modelo, canon_brand, canon_model, qty))

    updates.sort(key=lambda row: (row[0], row[1]))

    if updates:
        args.preview_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.preview_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["MarcaOriginal", "ModeloOriginal", "MarcaNueva", "ModeloNuevo", "Cantidad"])
            writer.writerows(updates)

    print(f"Total de combinaciones analizadas: {len(combos)}")
    print(f"Actualizaciones necesarias: {len(updates)}")
    if review:
        print("Revisar manualmente (se conservará la variante predominante):")
        for brand, norm, total, value in sorted(review, key=lambda x: (-x[2], x[0], x[1]))[:40]:
            print(f"  {brand} -> {norm} (total {total}) => {value}")

    if not args.apply:
        print(f"Vista previa guardada en: {args.preview_csv}")
        conn.close()
        return

    print("Aplicando cambios...")
    update_sql = "UPDATE Servicio SET Marca = ?, Modelo = ? WHERE Marca = ? AND Modelo = ?"
    for old_brand, old_model, new_brand, new_model, _ in updates:
        cursor.execute(update_sql, new_brand, new_model, old_brand, old_model)
    conn.commit()
    conn.close()
    print("Cambios aplicados correctamente.")


if __name__ == "__main__":
    main()
