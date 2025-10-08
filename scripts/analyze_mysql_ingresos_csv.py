import csv
import collections
from pathlib import Path

CSV_PATH = Path('backups/mysql_20251001_155856/ingresos.csv')

def main():
    counts = collections.Counter()
    with CSV_PATH.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for row in cr:
            u = row.get('ubicacion_id')
            if not u:
                continue
            try:
                uid = int(u)
            except Exception:
                continue
            counts[uid] += 1
    print('TOTAL_DISTINCT', len(counts))
    for uid, c in counts.most_common(20):
        print(uid, c)

if __name__ == '__main__':
    main()

