import csv
from pathlib import Path
from collections import Counter, defaultdict

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None

CSV_PATH = Path('backups/mysql_20251001_155856/ingresos.csv')
DB_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

def load_mysql_csv():
    idx = {}
    with CSV_PATH.open('r', encoding='utf-8', newline='') as f:
        cr = csv.DictReader(f)
        for row in cr:
            try:
                os_id = int(row['id'])
            except Exception:
                continue
            u = row.get('ubicacion_id')
            try:
                uid = int(u) if u else None
            except Exception:
                uid = None
            idx[os_id] = uid
    return idx

def load_access_flags():
    if pyodbc is None:
        return {}
    cn = pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={DB_PATH};", autocommit=True)
    cur = cn.cursor()
    cur.execute("SELECT Id, Alquilado FROM [Servicio]")
    flags = {}
    for row in cur.fetchall():
        try:
            os_id = int(row[0])
        except Exception:
            continue
        alquilado = bool(row[1]) if row[1] is not None else False
        flags[os_id] = alquilado
    cn.close()
    return flags

def main():
    my = load_mysql_csv()
    acc = load_access_flags()
    m = defaultdict(Counter)
    for os_id, uid in my.items():
        alquilado = acc.get(os_id, None)
        if alquilado is None:
            continue
        m[alquilado][uid] += 1
    print("Distribucion ubicacion_id segun Alquilado (Access):")
    for key in [True, False]:
        print(key, m[key])

if __name__ == '__main__':
    main()

