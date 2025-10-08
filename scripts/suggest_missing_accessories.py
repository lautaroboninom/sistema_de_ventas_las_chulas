from __future__ import annotations
import csv
import os
import re
import unicodedata
from collections import Counter

BACKUP_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\Nuevo Sistema de reparación\\backups\\mysql_20251001_155856\\ingresos.csv"
CATALOG_PATH = os.path.join('etl','out','catalogo_accesorios_mysql.csv')

def norm(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s

def main():
    # Load catalog set (normalized)
    catalog = set()
    with open(CATALOG_PATH, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            catalog.add(norm(row['nombre']))

    # Patterns and stopwords
    STOP = {
        'sin accesorios','s/ accesorios','c/ accesorios','accesorios ok','ok','--','-','n/a','na','ninguno','ninguna','ningunos',
        'completo','completa','completos','completas','varios accesorios','varios','ningun','ningun accesorio'
    }
    # Read backup ingresos
    cnt = Counter()
    if not os.path.exists(BACKUP_PATH):
        print('Backup no encontrado:', BACKUP_PATH)
        return 2
    with open(BACKUP_PATH, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            raw = (row.get('accesorios') or '').strip()
            if not raw:
                continue
            parts = re.split(r"[,;\u2013\u2014\-]+", raw)  # comma/semicolon/en dash/em dash/hyphen
            for p in parts:
                t = norm(p)
                t = re.sub(r"^(c/|s/|c\\|s\\)\s*", "", t)
                t = t.strip(' .')
                if not t or t in STOP:
                    continue
                if t in catalog:
                    continue
                # Heuristic short tokens we already cover via catalog categories
                if len(t) <= 2:
                    continue
                cnt[t] += 1
    # Show top 30 suggestions
    print('Sugerencias no presentes en catalogo (top 30):')
    for name, n in cnt.most_common(30):
        print(f" - {name} (x{n})")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

