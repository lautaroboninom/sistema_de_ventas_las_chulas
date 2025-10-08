import sys
from typing import List

try:
    import pyodbc  # type: ignore
except Exception as e:
    print("PYODBC_NOT_INSTALLED", e)
    sys.exit(0)

DB_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

TABLES_TO_PROBE: List[str] = [
    "RegistrosdeServicio",
    "Servicio",
]


def main():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={DB_PATH};"
    cn = pyodbc.connect(conn_str, autocommit=True)
    cur = cn.cursor()
    for t in TABLES_TO_PROBE:
        try:
            cur.execute(f"SELECT * FROM [{t}] WHERE 1=1")
        except Exception as e:
            print("TABLE_ERR", t, e)
            continue
        cols = [c[0] for c in cur.description]
        print("TABLE", t, "COLUMNS", ", ".join(cols))
        try:
            rows = cur.fetchmany(5)
            for r in rows:
                print("ROW", [r[i] for i in range(len(cols))])
        except Exception as e:
            print("READ_ERR", t, e)
    cn.close()

if __name__ == "__main__":
    main()

