# -*- coding: utf-8 -*-
import sys
import re
import unicodedata
import mysql.connector
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

REPO_ROOT = Path(r"Z:/Servicio Tecnico/1_SISTEMA REPARACIONES/Nuevo Sistema de reparación")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "mysqlroot",
    "database": "servicio_tecnico",
}

OUTPUT_PATH = REPO_ROOT / "tmp" / "canonical_brand_candidates.csv"


SOURCE_OVERRIDES = {
    "Inogen": "https://www.inogen.com/",
    "Longfian": "http://www.longfian.com/",
    "Philips": "https://www.philips.com/healthcare",
    "Philips Respironics": "https://www.usa.philips.com/healthcare/solutions/respiratory-care",
    "Fisher & Paykel": "https://www.fphcare.com/",
    "BMC Resmart": "https://global.bmc-medical.com/",
    "Movi-Vac": "https://www.movivac.com/",
    "Puritan Bennett": "https://www.medtronic.com/covidien/en-us/products/ventilation/puritan-bennett-560-ventilator.html",
    "Nellcor": "https://www.medtronic.com/covidien/en-us/products/pulse-oximetry-sensors.html",
    "ResMed": "https://www.resmed.com/",
    "Medical Healthy": "https://medicalhealthy.com/",
    "Electro Industria": "https://www.electroindustria.com.ar/",
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
})


def normalize_brand(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def canonicalize_brand(norm: str) -> str:
    if norm in MANUAL_CANONICAL_OVERRIDES:
        return MANUAL_CANONICAL_OVERRIDES[norm]
    parts = re.split(r"[\s\-/]+", norm)
    canonical = " ".join(
        part.capitalize() if len(part) > 3 else part.upper()
        for part in parts if part
    )
    return canonical


def slugify(name: str) -> str:
    value = unicodedata.normalize("NFKD", name)
    value = ''.join(c for c in value if unicodedata.category(c) != 'Mn')
    value = re.sub(r"[^0-9A-Za-z]+", "", value)
    return value.lower()


def lookup_source_url(canonical_name: str) -> str:
    if canonical_name in SOURCE_OVERRIDES:
        return SOURCE_OVERRIDES[canonical_name]
    query = f"{canonical_name} medical equipment"
    try:
        resp = SESSION.get("https://duckduckgo.com/html/", params={"q": query}, timeout=10)
        resp.raise_for_status()
    except Exception:
        return "PENDING"
    soup = BeautifulSoup(resp.text, "html.parser")
    slug = slugify(canonical_name)
    for link in soup.select("a.result__a"):
        href = link.get("href")
        if not href:
            continue
        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        if not domain:
            continue
        if slug[:5] in domain.replace('-', '').replace('.', ''):
            return href
    # fallback: first result
    first = soup.select_one("a.result__a")
    if first and first.get("href"):
        return first["href"]
    return "PENDING"


conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("""
    SELECT m.id, m.nombre, COUNT(d.id) AS device_count
    FROM marcas m
    LEFT JOIN devices d ON d.marca_id = m.id
    GROUP BY m.id, m.nombre
    ORDER BY device_count DESC
""")
rows = cur.fetchall()
conn.close()

records = []
seen = {}
for mid, name, count in rows:
    norm = normalize_brand(name)
    canonical = canonicalize_brand(norm)
    if canonical not in seen:
        source_url = lookup_source_url(canonical)
        seen[canonical] = {
            "canonical_name": canonical,
            "source_url": source_url,
            "aliases": set(),
            "total_devices": 0,
        }
    entry = seen[canonical]
    entry["aliases"].add(name)
    entry["total_devices"] += count or 0

records = [
    {
        "canonical_name": data["canonical_name"],
        "source_url": data["source_url"],
        "aliases": " | ".join(sorted(data["aliases"])),
        "total_devices": data["total_devices"]
    }
    for data in seen.values()
]

records.sort(key=lambda item: item["canonical_name"])

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
    fh.write("canonical_name,source_url,total_devices,aliases\n")
    for row in records:
        fh.write(
            f"{row['canonical_name']},{row['source_url']},{row['total_devices']},\"{row['aliases']}\"\n"
        )

print(f"Generated {len(records)} canonical brand candidates -> {OUTPUT_PATH}")
