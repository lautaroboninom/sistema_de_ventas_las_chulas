import sys

try:
    import pyodbc  # type: ignore
except Exception as e:
    print("PYODBC_NOT_INSTALLED", e)
    sys.exit(0)

DB_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

def main():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={DB_PATH};"
    try:
        cn = pyodbc.connect(conn_str, autocommit=True)
    except Exception as e:
        print("ACCESS_CONN_ERR", e)
        sys.exit(1)
    try:
        cur = cn.cursor()
        tables = [row.table_name for row in cur.tables(tableType='TABLE')]
        print("TABLE_COUNT", len(tables))
        for t in tables:
            print("TABLE", t)
    finally:
        try:
            cn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()

